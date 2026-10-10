#!/usr/bin/env python3
"""Aggregate the per-leg metadata of one run and decide about the release.

Source of truth for the artifact/output shapes: change producers
(`github.yaml`, "Write update metadata") and this script together.

Per-leg meta (`*-meta.json`): name, workdir, mode, changed, published, alias,
digest, versions, image, ghcr_image, tip_sha.

`collect_updates.py body` renders the release body once the final state commit
is known (env STATE_SHA).

Environment:
  UPDATES_DIR        directory with the downloaded `*-meta.json` (default /tmp/updates)
  EXPECTED_WORKDIRS  JSON array of workdirs that must have produced a meta (optional)
  REMOTE             git remote used for the tag lookup (default origin)
  RELEASE_BODY_FILE  where to write the release body (default /tmp/release-body.md)
  GITHUB_OUTPUT      step outputs file
"""

import glob
import json
import os
import subprocess
import sys
from typing import Callable, Optional


def as_bool(value) -> bool:
    return str(value).lower() == "true"


def norm_workdir(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("./"):
        value = value[2:]
    value = value.rstrip("/")
    return "." if value in ("", ".") else value


def load_metas(updates_dir: str) -> list:
    metas = []
    for meta_file in sorted(glob.glob(os.path.join(updates_dir, "*-meta.json"))):
        with open(meta_file, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
        meta["workdir"] = norm_workdir(meta.get("workdir", "."))
        meta["changed"] = as_bool(meta.get("changed", "false"))
        meta["published"] = as_bool(meta.get("published", "false"))
        metas.append(meta)
    metas.sort(key=lambda m: m["workdir"].lower())
    return metas


def git_tag_missing(tag: str, remote: str = "origin") -> bool:
    """True when `tag` does not exist on the remote; any git failure raises."""
    result = subprocess.run(
        ["git", "ls-remote", "--tags", remote, f"refs/tags/{tag}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() == ""


def release_body(metas: list, combined_tag: str, state_sha: str = "") -> str:
    """Deterministic release body: no timestamps or run ids, so an unchanged
    state renders to identical text and a re-run edits nothing."""
    lines = [f"Automated release for `{combined_tag}`.", ""]
    lines.append(
        "The image tags move: they are rebuilt and re-pushed when the base image or a "
        "dependency changes. The digest identifies an exact build."
    )
    lines.append("")
    for meta in metas:
        lines.append(f"### {meta['workdir']}")
        lines.append(f"- tag: `{meta.get('alias', '')}`")
        if meta.get("digest"):
            lines.append(f"- digest: `{meta['digest']}`")
        if meta.get("image"):
            lines.append(f"- docker.io: `{meta['image']}`")
        if meta.get("ghcr_image"):
            lines.append(f"- ghcr.io: `{meta['ghcr_image']}`")
        versions = meta.get("versions") or {}
        if versions:
            lines.append("- versions:")
            for key, value in versions.items():
                lines.append(f"  - {key}: `{value}`")
        lines.append("")
    if state_sha:
        lines.append(f"State commit: `{state_sha}`")
        lines.append("")
        lines.append(f"<!-- cicd-state-sha: {state_sha} -->")
    return "\n".join(lines) + "\n"


def aggregate(
    metas: list,
    expected: list,
    tag_missing_fn: Callable[[str], bool],
) -> dict:
    """Pure decision logic; returns the step outputs (raises ValueError on conflict).

    The git tag/release is named by the legs' image tags, which carry only the
    main versions. A missing tag means a main version changed (or the repo was
    never released): create tag + release. An existing tag means a dependency or
    base-only change: the existing release body is refreshed, nothing is created.
    """
    metas = sorted(metas, key=lambda m: m["workdir"].lower())
    expected = [norm_workdir(w) for w in expected]
    present = {m["workdir"] for m in metas}
    blocking = [w for w in expected if w not in present]

    tips = {m.get("tip_sha", "") for m in metas}
    if len(tips) > 1:
        raise ValueError(f"Legs built different commits: {sorted(tips)}")
    tip_sha = tips.pop() if tips else ""

    combined_tag = "-".join(m["alias"] for m in metas if m.get("alias"))
    tag_missing = bool(combined_tag) and tag_missing_fn(combined_tag)
    published_any = any(m["published"] for m in metas)
    blocked = bool(blocking) and (tag_missing or published_any)
    return {
        "meta_found": bool(metas),
        "combined_tag": combined_tag,
        "tip_sha": tip_sha,
        "tag_missing": tag_missing,
        "published_any": published_any,
        "blocking": blocking,
        "release_needed": tag_missing and not blocking,
        "blocked": blocked,
    }


def write_summary(result: dict) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("### Release decision\n")
        for key in (
            "combined_tag",
            "tag_missing",
            "published_any",
            "release_needed",
        ):
            handle.write(f"- {key}: `{result[key]}`\n")
        if result["blocking"]:
            handle.write(
                f"- **blocked by legs that produced no result: "
                f"{', '.join(result['blocking'])}**\n"
            )


def body_main() -> int:
    """`collect_updates.py body`: write the release body for the final state commit."""
    metas = load_metas(os.environ.get("UPDATES_DIR", "/tmp/updates"))
    combined = "-".join(m["alias"] for m in metas if m.get("alias"))
    body_file = os.environ.get("RELEASE_BODY_FILE", "/tmp/release-body.md")
    with open(body_file, "w", encoding="utf-8") as handle:
        handle.write(release_body(metas, combined, os.environ.get("STATE_SHA", "")))
    return 0


def main(argv: Optional[list] = None) -> int:
    if (sys.argv[1:] if argv is None else argv)[:1] == ["body"]:
        return body_main()
    updates_dir = os.environ.get("UPDATES_DIR", "/tmp/updates")
    remote = os.environ.get("REMOTE", "origin")
    expected_raw = os.environ.get("EXPECTED_WORKDIRS", "").strip()
    expected = json.loads(expected_raw) if expected_raw else []

    metas = load_metas(updates_dir)
    if not metas:
        print(
            f"::error::No update metadata found in {updates_dir}; "
            "the per-target jobs produced no artifacts.",
            file=sys.stderr,
        )
        return 1

    try:
        result = aggregate(metas, expected, lambda t: git_tag_missing(t, remote))
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    if result["blocking"]:
        print(
            "::error::No result from leg(s): " + ", ".join(result["blocking"]),
            file=sys.stderr,
        )

    write_summary(result)

    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        print("GITHUB_OUTPUT not set", file=sys.stderr)
        return 1
    with open(output, "a", encoding="utf-8") as handle:
        for key, value in result.items():
            if isinstance(value, bool):
                value = str(value).lower()
            elif isinstance(value, list):
                value = ",".join(value)
            handle.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
