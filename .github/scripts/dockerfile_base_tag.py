#!/usr/bin/env python3
import argparse
import sys

from dockerfile_parse import DockerfileParser


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract base image tag from a Dockerfile."
    )
    parser.add_argument(
        "--path",
        default="Dockerfile",
        help="Path to the Dockerfile (default: Dockerfile in CWD)",
    )
    args = parser.parse_args()

    parser = DockerfileParser(path=args.path)
    base = (parser.baseimage or "").strip()
    if not base:
        print("No base image found in Dockerfile", file=sys.stderr)
        return 1

    image_no_digest = base.split("@", 1)[0]
    slash = image_no_digest.rfind("/")
    colon = image_no_digest.rfind(":")
    tag = image_no_digest[colon + 1 :] if colon > slash else "latest"
    print(tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
