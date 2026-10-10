#!/usr/bin/env python3
import argparse


def normalize_workdir(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("./"):
        value = value[2:]
    value = value.rstrip("/")
    if value in ("", "."):
        return "."
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute latest-tag ownership flags for workflow targets."
    )
    parser.add_argument(
        "--current-workdir",
        default=".",
        help="Current matrix target workdir",
    )
    parser.add_argument(
        "--latest-tag-workdir",
        default="",
        help="Optional configured subdirectory to own latest when no root target exists",
    )
    args = parser.parse_args()

    current_workdir = normalize_workdir(args.current_workdir)
    configured_latest_workdir = ""
    if args.latest_tag_workdir:
        configured_latest_workdir = normalize_workdir(args.latest_tag_workdir)

    # Each leg is its own workflow call: a root target exists iff this leg is it.
    root_target_exists = current_workdir == "."

    apply_latest_tag = False
    latest_tag_owner = "none"
    if root_target_exists:
        if current_workdir == ".":
            apply_latest_tag = True
            latest_tag_owner = "root"
    elif configured_latest_workdir and current_workdir == configured_latest_workdir:
        apply_latest_tag = True
        latest_tag_owner = "configured-subdirectory"

    print(f"ROOT_TARGET_EXISTS={str(root_target_exists).lower()}")
    print(f"LATEST_TAG_WORKDIR={configured_latest_workdir}")
    print(f"APPLY_LATEST_TAG={str(apply_latest_tag).lower()}")
    print(f"LATEST_TAG_OWNER={latest_tag_owner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
