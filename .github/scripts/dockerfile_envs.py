#!/usr/bin/env python3
import argparse
import json
import re
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


TAG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")


def normalize_folder(folder: str) -> str:
    folder = (folder or "").strip()
    if folder.startswith("./"):
        folder = folder[2:]
    folder = folder.rstrip("/")
    return "" if folder in ("", ".") else folder


def validate_tag(tag: str, what: str) -> None:
    if not TAG_RE.match(tag):
        raise ValueError(
            f"{what} {tag!r} is not a valid image tag "
            "(allowed: [A-Za-z0-9_.-], max 128 chars, no leading '.' or '-')"
        )


def sanitize_tag_part(value: str) -> str:
    """Replace characters illegal in an image tag (and spaces) with `-`.

    A leading '.' or '-' is not allowed in a tag either; it becomes '_'.
    """
    value = re.sub(r"[^A-Za-z0-9._-]", "-", (value or "").strip())
    return re.sub(r"^[.-]", "_", value)


def build_alias(envs: dict, main: str, folder: str) -> str:
    """Return the image tag `[<folder>-]<main value>` (the main software only).

    Characters that are illegal in a tag are replaced with `-`; the result is
    validated, so an empty value or an over-long tag is a hard error.
    """
    if not main:
        raise ValueError("IMAGE_TAG (the ENV name of the main software) is not set")
    if main not in envs:
        raise ValueError(f"Environment variable '{main}' not found in Dockerfile")
    tag = sanitize_tag_part(envs[main])
    folder = normalize_folder(folder)
    if folder:
        validate_tag(folder, "Folder name")
        tag = f"{folder}-{tag}"
    validate_tag(tag, "Image tag")
    return tag


def build_versions(envs: dict, base: str) -> dict:
    """`*_VERSION` values in Dockerfile order, plus the base image tag as `BASE`."""
    versions = {k: v for k, v in envs.items() if k.endswith("_VERSION")}
    if base:
        versions["BASE"] = base
    return versions


def cmd_alias(envs: dict, args: argparse.Namespace) -> int:
    try:
        print(build_alias(envs, args.main, args.folder))
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


def cmd_versions(envs: dict, args: argparse.Namespace) -> int:
    print(json.dumps(build_versions(envs, args.base)))
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
    subparsers.add_parser("list", help="Print ENV values as KEY=VALUE lines.")
    subparsers.add_parser("json", help="Print ENV values as JSON.")
    alias_parser = subparsers.add_parser(
        "alias", help="Print the image tag: [folder-]<main version>."
    )
    alias_parser.add_argument(
        "--main", default="", help="ENV name of the main software"
    )
    alias_parser.add_argument("--folder", default=".", help="Workdir ('.' for none)")
    versions_parser = subparsers.add_parser(
        "versions", help="Print the *_VERSION values (and BASE) as JSON."
    )
    versions_parser.add_argument("--base", default="", help="Base image tag")

    args = parser.parse_args()
    envs = collect_envs(args.path)

    if args.command == "get":
        return cmd_get(envs, args.name)
    if args.command == "versions":
        return cmd_versions(envs, args)
    if args.command == "alias":
        return cmd_alias(envs, args)
    if args.command == "list":
        return cmd_list(envs)
    if args.command == "json":
        return cmd_json(envs)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
