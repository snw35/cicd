#!/usr/bin/env python3
import argparse
import json
import sys

from dockerfile_parse import DockerfileParser
from dockerfile_parse.util import extract_key_values


def collect_envs(path: str) -> dict:
    parser = DockerfileParser(path=path)
    envs = {}
    stage_envs = {}
    stage_args = {}
    global_args = {}
    in_stage = False

    for instruction in parser.structure:
        inst = instruction.get("instruction")
        value = instruction.get("value")

        if inst == "FROM":
            in_stage = True
            stage_envs = {}
            stage_args = {}
        elif inst == "ARG":
            for key, val in extract_key_values(False, stage_args, stage_envs, value):
                if in_stage:
                    if key in global_args:
                        val = global_args[key]
                    stage_args[key] = val
                else:
                    global_args[key] = val
        elif inst == "ENV":
            for key, val in extract_key_values(True, stage_args, stage_envs, value):
                stage_envs[key] = val
                envs[key] = val

    return envs


def cmd_get(envs: dict, name: str) -> int:
    value = envs.get(name)
    if value is None:
        print(f"Environment variable '{name}' not found in Dockerfile", file=sys.stderr)
        return 1
    print(value)
    return 0


def cmd_versions(envs: dict) -> int:
    suffix = "_VERSION"
    versions = [value for key, value in envs.items() if key.endswith(suffix)]
    print("-".join(versions))
    return 0


def cmd_list(envs: dict) -> int:
    for key, value in envs.items():
        print(f"{key}={value}")
    return 0


def cmd_json(envs: dict) -> int:
    print(json.dumps(envs))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract ENV values from a Dockerfile."
    )
    parser.add_argument(
        "--path",
        default="Dockerfile",
        help="Path to the Dockerfile (default: Dockerfile in CWD)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    get_parser = subparsers.add_parser("get", help="Get a single ENV value.")
    get_parser.add_argument("name")
    subparsers.add_parser("versions", help="Print concatenated *_VERSION values.")
    subparsers.add_parser("list", help="Print ENV values as KEY=VALUE lines.")
    subparsers.add_parser("json", help="Print ENV values as JSON.")

    args = parser.parse_args()
    envs = collect_envs(args.path)

    if args.command == "get":
        return cmd_get(envs, args.name)
    if args.command == "versions":
        return cmd_versions(envs)
    if args.command == "list":
        return cmd_list(envs)
    if args.command == "json":
        return cmd_json(envs)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
