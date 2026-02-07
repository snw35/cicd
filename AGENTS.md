# AI Context: cicd

This repository provides reusable GitHub Actions workflows to automate container
updates using `nvchecker` and `dfupdate`.

## Branches

The primary branch is `main`, and the primary branch that all downstream respositories will use is also `main`.
Feature branches will be named after their purpose, e.g `add-lint-checks` or similar.

## What lives where
- `.github/workflows/github.yaml`: reusable workflow for build, update, tag, and publish.
- `.github/workflows/create-release.yaml`: aggregates per-target updates and creates releases.
- `.github/workflows/integration-pr.yaml`: PR check that dispatches the upstream integration workflow.
- `.github/scripts/`: helper scripts used by the workflows for tag/metadata processing.
- `integration-test/`: sample Dockerfile and nvchecker config for testing.

## Key inputs/outputs (workflow_call)
- Inputs: `WORKDIR`, `TARGETS_JSON`, `IMAGE_TAG`, `TAG_COMMAND`, `CICD_REF`.
- Outputs: `changed`, `docker_tag`, `proposed_tag`, `image`, `targets`.

## High-level flow
- Pull requests only build a container image (no updates or publishing) and
  dispatch the upstream integration workflow for same-repo PRs.
- The PR integration workflow creates an ephemeral branch in
  `snw35/cicd-integration`, rewrites
  `.github/workflows/integration-update.yaml` on that branch to pin
  `snw35/cicd/.github/workflows/github.yaml` and
  `snw35/cicd/.github/workflows/create-release.yaml` to the PR head SHA,
  dispatches the integration workflow on that ephemeral branch, and polls until
  completion.
- Scheduled/manual runs:
  - Run `nvchecker` and `dfupdate`.
  - Compute tag metadata and check for existing tags.
  - Build/test/push images if changes exist or the tag is missing.
  - Package changes and metadata as artifacts for aggregation.
- Release workflow aggregates per-target patches, commits, and creates a combined tag.

## Workflow decision matrix
For reusable workflows, `github.event_name` reflects the caller event.

| Workflow | Event | Job | If condition | Outputs |
| --- | --- | --- | --- | --- |
| `.github/workflows/github.yaml` | pull_request | build-only | `github.event_name == 'pull_request'` | - |
| `.github/workflows/github.yaml` | schedule, workflow_dispatch | container-update | `github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'` | - |
| `.github/workflows/github.yaml` | schedule, workflow_dispatch | collect-metadata | `(github.event_name == 'schedule' || github.event_name == 'workflow_dispatch') && needs.container-update.result != 'failure'` | `changed_any`, `docker_tags`, `proposed_tags`, `images`, `targets_json` (feeds workflow outputs) |
| `.github/workflows/create-release.yaml` | workflow_call (any caller event) | aggregate-changes | - | `changed_any`, `docker_tags`, `proposed_tags`, `images`, `targets_json`, `meta_found`, `committed` |
| `.github/workflows/create-release.yaml` | workflow_call (any caller event) | create-release | `needs.aggregate-changes.outputs.changed_any == 'true'` | `tag` (feeds workflow output) |
| `.github/workflows/integration-pr.yaml` | pull_request | integration | `github.event.pull_request.head.repo.full_name == github.repository` | - |
| `.github/workflows/lint-actions.yaml` | pull_request | actionlint | - | - |

## Cross-repo token requirements
- Secret: `CICD_INTEGRATION_TOKEN` (configured in `snw35/cicd`).
- Fine-grained PAT scope: repository `snw35/cicd-integration` only.
- Required repository permissions (least privilege):
  - **Actions: Read and write**
    - dispatch `integration-update.yaml`
    - list/get workflow runs for polling
  - **Contents: Read and write**
    - read base branch workflow content
    - create/update ephemeral branch refs
    - write rewritten workflow file on ephemeral branch

## Helper scripts
- `dockerfile_base_tag.py`: extracts base image tag from the Dockerfile.
- `dockerfile_envs.py`: reads `ENV` values from the Dockerfile for tagging.
- `collect_updates.py`: merges per-target metadata into workflow outputs.
- `pick_release_tag.py`: computes a combined release tag from changed targets.

## Local troubleshooting (from README)
```
podman run --security-opt label=disable --userns keep-id -it --rm --name nvchecker --mount type=bind,source=${PWD},target=/data/ -w /data snw35/nvchecker:2.9 nvchecker -l debug -c nvchecker.toml

podman run --security-opt label=disable --userns keep-id -it --rm --name dfupdate --mount type=bind,source=${PWD},target=/data/ -w /data snw35/dfupdate:0.2.0
```
