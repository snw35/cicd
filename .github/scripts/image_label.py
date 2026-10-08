#!/usr/bin/env python3
"""Print one label from `docker buildx imagetools inspect <ref> --format '{{json .Image}}'`.

Reads the JSON on stdin. Handles a single-manifest config (`{"config": {"Labels":
{...}}}`) and a multi-platform map (`{"linux/amd64": {...}}`); for a map every
platform must agree, otherwise the value is empty (treated as stale). Prints an
empty string when the label is absent.

Usage: image_label.py <label>
"""

import json
import sys


def find_labels(node) -> list:
    """All `Labels` dicts found in an inspect result."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() == "labels" and isinstance(value, dict):
                found.append(value)
            else:
                found.extend(find_labels(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(find_labels(item))
    return found


def label_value(inspect_json: str, label: str) -> str:
    values = {labels.get(label, "") for labels in find_labels(json.loads(inspect_json))}
    return values.pop() if len(values) == 1 else ""


if __name__ == "__main__":
    print(label_value(sys.stdin.read(), sys.argv[1]))
