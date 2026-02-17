#!/usr/bin/env python3
import argparse
import json
from typing import Optional


def normalize_workdir(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("./"):
        value = value[2:]
    value = value.rstrip("/")
    if value in ("", "."):
        return "."
    return value


def detect_root_target(targets_json: str) -> Optional[bool]:
    if not targets_json:
        return None

    try:
        targets = json.loads(targets_json)
    except Exception:
        return False

    if not isinstance(targets, list):
        return False

    for target in targets:
        if not isinstance(target, dict):
            continue
        if normalize_workdir(str(target.get("workdir", "."))) == ".":
            return True

    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute latest-tag ownership flags for workflow targets."
    )
    parser.add_argument(
        "--targets-json", default="", help="JSON array of target objects"
    )
    parser.add_argument(
        "--input-workdir",
        default=".",
        help="Workflow input WORKDIR fallback when TARGETS_JSON is empty",
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

    root_from_targets = detect_root_target(args.targets_json)
    if root_from_targets is None:
        root_target_exists = normalize_workdir(args.input_workdir) == "."
    else:
        root_target_exists = root_from_targets

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
