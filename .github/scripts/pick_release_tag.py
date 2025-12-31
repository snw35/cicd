#!/usr/bin/env python3
import json
import os
import sys


def main() -> int:
    targets_json = os.environ.get("TARGETS_JSON", "")
    if not targets_json:
        print("")
        return 0

    try:
        targets = json.loads(targets_json)
    except json.JSONDecodeError as exc:
        print(f"Invalid TARGETS_JSON: {exc}", file=sys.stderr)
        return 1

    changed = [
        t
        for t in targets
        if str(t.get("changed", "false")).lower() == "true"
        or str(t.get("tag_exists", "false")).lower() != "true"
    ]
    if not changed:
        print("")
        return 0

    changed.sort(
        key=lambda t: ((t.get("workdir") or "").lower(), (t.get("name") or "").lower())
    )

    segments = []
    for target in changed:
        docker_tag = target.get("docker_tag") or target.get("proposed_tag")
        if docker_tag:
            segments.append(docker_tag)

    if not segments:
        print("")
        return 0

    print("-".join(segments))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
