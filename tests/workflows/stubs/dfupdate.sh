#!/usr/bin/env bash
set -euo pipefail

version="${CICD_TEST_VERSION:-9.9.9}"
if [ -f version.txt ]; then
  version="$(cat version.txt)"
fi

if [ ! -f Dockerfile ]; then
  echo "Dockerfile not found in $(pwd)" >&2
  exit 1
fi

if grep -q '^ENV [A-Za-z0-9_]*_VERSION=' Dockerfile; then
  sed -i "s/^ENV \([A-Za-z0-9_]*_VERSION\)=.*/ENV \1=${version}/" Dockerfile
else
  echo "No *_VERSION ENV found in Dockerfile" >&2
  exit 1
fi
