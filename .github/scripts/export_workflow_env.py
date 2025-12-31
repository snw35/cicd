#!/usr/bin/env python3
import argparse
import os
import sys

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export workflow env keys into GITHUB_ENV."
    )
    parser.add_argument(
        "--workflow",
        required=True,
        help="Path to workflow YAML file to read env from.",
    )
    parser.add_argument(
        "--keys",
        nargs="+",
        required=True,
        help="Env keys to export from the workflow.",
    )
    args = parser.parse_args()

    workflow_path = args.workflow
    data = yaml.safe_load(open(workflow_path, "r", encoding="utf-8"))
    env = data.get("env", {}) if isinstance(data, dict) else {}
    missing = [key for key in args.keys if key not in env]
    if missing:
        print(
            f"Missing keys in workflow env: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    env_file = os.environ.get("GITHUB_ENV")
    if not env_file:
        print("GITHUB_ENV not set", file=sys.stderr)
        return 1

    with open(env_file, "a", encoding="utf-8") as handle:
        for key in args.keys:
            handle.write(f"{key}={env[key]}\n")
            print(f"export {key}={env[key]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
