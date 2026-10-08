#!/usr/bin/env python3
"""Bump a date-based main version (opt-in `DATE_VERSION`, e.g. a devcontainer-style
image bundling many packages with no single main one).

The main-version ENV (named by IMAGE_TAG) holds `YYYY-MM-DD` or `YYYY-MM-DD-N`
literally in the Dockerfile. After dfupdate, when the Dockerfile differs from
HEAD, `bump` rewrites it to the run date (UTC); a second bump on the same date
becomes `-2`, `-3`, ... Without a Dockerfile change nothing is touched, so
re-runs and hand fixes keep the tag.

The ENV must occur exactly once and hold a valid value in both modes, so a hand
edit such as `2026-10-04-hotfix` fails loudly. A newly computed version whose image
tag already exists on Docker Hub (history reset) is incremented until it is free.

Usage: date_version.py --path Dockerfile --main CLOUDENV_VERSION --run-date YYYY-MM-DD
       [--no-bump] [--repo owner/name --folder cu12]
`--no-bump` (publish mode) only validates. Prints the version. Needs git; run in
the checkout.
"""

import argparse
import re
import subprocess
import sys

VERSION_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-([1-9]\d*))?$")


def next_version(current: str, run_date: str) -> str:
    """Version for a change made on `run_date`, given the valid committed `current`.

    An older date moves to `run_date`; the same (or a hand-set later) date gets the
    next ordinal, so the version never goes backwards.
    """
    match = VERSION_RE.match(current)
    if not match:
        raise ValueError(f"{current!r} is not YYYY-MM-DD or YYYY-MM-DD-N")
    date, ordinal = match.group(1), int(match.group(2) or 1)
    if date < run_date:
        return run_date
    return f"{date}-{ordinal + 1}"


def bump_ordinal(version: str) -> str:
    match = VERSION_RE.match(version)
    return f"{match.group(1)}-{int(match.group(2) or 1) + 1}"


def env_line_re(name: str) -> "re.Pattern[str]":
    # `ENV NAME value` or `ENV NAME=value` (first key of the instruction)
    return re.compile(rf"^(\s*ENV\s+{re.escape(name)}(?:\s+|=))(\S+)(.*)$")


def read_current(text: str, name: str) -> str:
    """The ENV's value; it must occur exactly once and be a valid date version."""
    pattern = env_line_re(name)
    values = [
        m.group(2).strip("\"'")
        for m in (pattern.match(line) for line in text.splitlines())
        if m
    ]
    if len(values) != 1:
        raise ValueError(f"ENV {name} must occur exactly once ({len(values)} found)")
    if not VERSION_RE.match(values[0]):
        raise ValueError(
            f"ENV {name} value {values[0]!r} is not YYYY-MM-DD or YYYY-MM-DD-N"
        )
    return values[0]


def rewrite(text: str, name: str, new: str) -> str:
    pattern = env_line_re(name)
    out = []
    for line in text.splitlines(keepends=True):
        match = pattern.match(line.rstrip("\n"))
        if match:
            ending = "\n" if line.endswith("\n") else ""
            line = f"{match.group(1)}{new}{match.group(3)}{ending}"
        out.append(line)
    return "".join(out)


def dockerfile_changed(path: str) -> bool:
    return (
        subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path]).returncode == 1
    )


def tag_exists(ref: str) -> bool:
    """True if the image tag exists; 'manifest unknown' means free, other errors raise."""
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", ref],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    if re.search(
        r"no such manifest|manifest unknown|name unknown|not found",
        result.stderr,
        re.IGNORECASE,
    ):
        return False
    raise RuntimeError(f"cannot read {ref}: {result.stderr.strip()}")


def first_free(repo: str, prefix: str, version: str) -> str:
    """Increment the ordinal until `repo:prefix+version` is not on the registry."""
    while repo and tag_exists(f"{repo}:{prefix}{version}"):
        version = bump_ordinal(version)
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="Dockerfile")
    parser.add_argument("--main", required=True, help="ENV name of the main version")
    parser.add_argument("--run-date", required=True, help="UTC date, YYYY-MM-DD")
    parser.add_argument("--no-bump", action="store_true", help="validate only")
    parser.add_argument("--repo", default="", help="owner/name for the collision check")
    parser.add_argument("--folder", default=".", help="workdir prefix of the tag")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.run_date):
        print(f"::error::Bad --run-date {args.run_date!r}", file=sys.stderr)
        return 1
    with open(args.path, encoding="utf-8") as handle:
        text = handle.read()
    try:
        current = read_current(text, args.main)
        if args.no_bump or not dockerfile_changed(args.path):
            print(current)
            return 0
        new = next_version(current, args.run_date)
        folder = args.folder.strip("./")
        prefix = f"{folder}-" if folder else ""
        new = first_free(args.repo, prefix, new)
    except (ValueError, RuntimeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    with open(args.path, "w", encoding="utf-8") as handle:
        handle.write(rewrite(text, args.main, new))
    print(new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
