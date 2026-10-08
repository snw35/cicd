#!/usr/bin/env python3
"""Plan job helper and per-leg staleness check.

`select_legs.py` (no argument), plan job: fetch the default-branch tip once and
print it as `tip_sha`, plus `run_date` (today, UTC; GITHUB_OUTPUT). Env: DEFAULT_BRANCH, GITHUB_OUTPUT.

`select_legs.py stale <workdir> <label_sha>`, leg: print `true` when the image
built from commit `label_sha` (its `org.opencontainers.image.revision` label)
may be out of date for this leg: no label, a label that is not an ancestor of
HEAD, or non-bot, non-ignored paths changed in `label_sha..HEAD` that select
this leg. Env: WORKDIRS (JSON array of all workdirs of the caller).
"""

import datetime
import json
import os
import posixpath
import subprocess
import sys
from typing import Callable, Optional

BOT_SUBJECT = "Automated container updates"
IGNORED_BASENAMES = {"LICENSE", "old_ver.json", "new_ver.json", "nvchecker.toml"}


def norm_workdir(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("./"):
        value = value[2:]
    value = value.rstrip("/")
    return "." if value in ("", ".") else value


def is_ignored(path: str) -> bool:
    if path.startswith(".github/"):
        return True
    base = posixpath.basename(path)
    return base.endswith(".md") or base in IGNORED_BASENAMES


def select_legs(workdirs: list, paths: list) -> list:
    """Legs (in `workdirs` order) selected by the non-ignored changed `paths`."""
    workdirs = [norm_workdir(w) for w in workdirs]
    non_root = [w for w in workdirs if w != "."]
    kept = [p for p in paths if p and not is_ignored(p)]

    def owner(path: str) -> Optional[str]:
        for workdir in non_root:
            if path.startswith(workdir + "/"):
                return workdir
        return None

    shared = any(owner(p) is None for p in kept)
    owned = {owner(p) for p in kept} - {None}
    selected = []
    for workdir in workdirs:
        if workdir == ".":
            if shared:
                selected.append(workdir)
        elif shared or workdir in owned:
            selected.append(workdir)
    return selected


def plan(
    workdirs: list,
    base: Optional[str],
    tip: str,
    is_ancestor: Callable[[str, str], bool],
    changed_paths: Callable[[str, str], list],
) -> list:
    """No `base` (no successful push run), a non-ancestor base (force-push) or a
    diff failure select every leg."""
    everything = [norm_workdir(w) for w in workdirs]
    if not base:
        return everything
    try:
        if not is_ancestor(base, tip):
            return everything
        return select_legs(workdirs, changed_paths(base, tip))
    except subprocess.CalledProcessError:
        return everything


def run(args: list) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def git_is_ancestor(base: str, tip: str) -> bool:
    result = subprocess.run(["git", "merge-base", "--is-ancestor", base, tip])
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise subprocess.CalledProcessError(result.returncode, "merge-base")


def git_changed_paths(base: str, tip: str) -> list:
    out = run(
        [
            "git",
            "log",
            "--no-merges",
            "--invert-grep",
            f"--grep=^{BOT_SUBJECT}$",
            "--name-only",
            "--format=",
            f"{base}..{tip}",
        ]
    )
    return sorted({line for line in out.splitlines() if line})


def stale_main(workdir: str, label_sha: str) -> int:
    workdirs = json.loads(os.environ["WORKDIRS"])
    leg = norm_workdir(workdir)
    if not label_sha:
        print("true")
        return 0
    subprocess.run(["git", "fetch", "--quiet", "origin", label_sha], check=False)
    selected = plan(workdirs, label_sha, "HEAD", git_is_ancestor, git_changed_paths)
    print("true" if leg in selected else "false")
    return 0


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "stale":
        return stale_main(sys.argv[2], sys.argv[3])
    branch = os.environ["DEFAULT_BRANCH"]
    try:
        run(["git", "fetch", "--quiet", "origin", branch])
        tip = run(["git", "rev-parse", "FETCH_HEAD"]).strip()
    except (subprocess.CalledProcessError, OSError) as exc:
        detail = getattr(exc, "stderr", "") or ""
        print(f"::error::Planning failed: {exc} {detail}", file=sys.stderr)
        return 1
    print(f"tip={tip}")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
        handle.write(f"tip_sha={tip}\n")
        handle.write(f"run_date={datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
