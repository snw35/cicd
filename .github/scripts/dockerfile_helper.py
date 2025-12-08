#!/usr/bin/env python3
"""
Helper utilities for extracting Dockerfile metadata using dockerfile-parse.
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, Tuple

from dockerfile_parse import DockerfileParser


def _load_parser(path: str) -> DockerfileParser:
    return DockerfileParser(path=path)


def _iter_env_items(parser: DockerfileParser) -> Iterable[Tuple[str, str]]:
    for key, value in parser.envs.items():
        yield key, value


def _env_versions(parser: DockerfileParser, suffix: str) -> None:
    versions = [value for key, value in _iter_env_items(parser) if key.endswith(suffix)]
    print("-".join(versions))


def _get_env(parser: DockerfileParser, name: str) -> None:
    for key, value in _iter_env_items(parser):
        if key == name:
            print(value)
            return

    sys.stderr.write(f"Environment variable '{name}' not found in Dockerfile\n")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read Dockerfile data using dockerfile-parse."
    )
    dockerfile_arg = argparse.ArgumentParser(add_help=False)
    dockerfile_arg.add_argument(
        "--dockerfile",
        default="Dockerfile",
        help="Path to the Dockerfile to inspect.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    env_versions = subparsers.add_parser(
        "env-versions",
        parents=[dockerfile_arg],
        help="Return hyphen-joined ENV values matching suffix.",
    )
    env_versions.add_argument(
        "--suffix",
        default="_VERSION",
        help="Suffix to match for ENV keys (default: %(default)s).",
    )

    get_env = subparsers.add_parser(
        "get-env",
        parents=[dockerfile_arg],
        help="Return the value for a specific ENV",
    )
    get_env.add_argument("name", help="ENV name to read from the Dockerfile.")

    args = parser.parse_args()

    df_parser = _load_parser(args.dockerfile)
    if args.command == "env-versions":
        _env_versions(df_parser, args.suffix)
    elif args.command == "get-env":
        _get_env(df_parser, args.name)


if __name__ == "__main__":
    main()
