#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ACT_BIN="${ACT_BIN:-act}"
ENV_FILE="${ROOT}/tests/workflows/act.env"
SECRETS_FILE="${ROOT}/tests/workflows/act.secrets"
EVENT_WORKFLOW_CALL="${ROOT}/tests/workflows/events/workflow_call.json"
EVENT_WORKFLOW_CALL_CREATE_RELEASE="${ROOT}/tests/workflows/events/workflow_call_create_release.json"
EVENT_WORKFLOW_DISPATCH="${ROOT}/tests/workflows/events/workflow_dispatch.json"
ACT_IMAGE="${ACT_IMAGE:-ghcr.io/catthehacker/ubuntu:act-latest}"

cd "${ROOT}"

if ! command -v "${ACT_BIN}" >/dev/null 2>&1; then
  echo "act not found in PATH (set ACT_BIN to override)" >&2
  exit 1
fi

echo "Using ACT_IMAGE=${ACT_IMAGE}"

reset_fixtures() {
  cat > "${ROOT}/tests/workflows/fixtures/workdir/Dockerfile" <<'DOCKERFILE'
FROM alpine:3.22

ENV SAMPLE_VERSION=1.2.3
DOCKERFILE

  cat > "${ROOT}/tests/workflows/fixtures/workdir/old_ver.json" <<'JSON'
{
  "sample": {
    "version": "1.2.3"
  }
}
JSON

  cat > "${ROOT}/tests/workflows/fixtures/workdir/version.txt" <<'VERSION'
2.3.4
VERSION

  rm -f "${ROOT}/tests/workflows/fixtures/workdir/new_ver.json"

  cat > "${ROOT}/tests/workflows/fixtures/release-target.txt" <<'TEXT'
before
TEXT
}

run_act() {
  local workflow="$1"
  local event_name="$2"
  local event="$3"

  "${ACT_BIN}" "${event_name}" \
    -W "${workflow}" \
    -e "${event}" \
    --secret-file "${SECRETS_FILE}" \
    --env-file "${ENV_FILE}" \
    -P "ubuntu-latest=${ACT_IMAGE}"
}

reset_fixtures

run_act "${ROOT}/.github/workflows/github.yaml" "workflow_call" "${EVENT_WORKFLOW_CALL}"
run_act "${ROOT}/.github/workflows/create-release.yaml" "workflow_call" "${EVENT_WORKFLOW_CALL_CREATE_RELEASE}"
run_act "${ROOT}/.github/workflows/integration-test.yaml" "workflow_dispatch" "${EVENT_WORKFLOW_DISPATCH}"

reset_fixtures
