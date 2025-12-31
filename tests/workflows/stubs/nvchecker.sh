#!/usr/bin/env bash
set -euo pipefail

version="${CICD_TEST_VERSION:-9.9.9}"

cat > new_ver.json <<JSON
{
  "sample": {
    "version": "${version}"
  }
}
JSON
