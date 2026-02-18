# AI Context: cicd

This repository provides reusable GitHub Actions workflows to automate container
updates using `nvchecker` and `dfupdate`.

## Branches

The primary branch is `main`, and the primary branch that all downstream repositories will use is also `main`.
Feature branches will be named after their purpose, e.g `add-lint-checks` or similar.

## What lives where
- `.github/workflows/github.yaml`: reusable workflow for build, update, tag, and publish.
- `.github/workflows/create-release.yaml`: aggregates per-target updates and creates releases.
- `.github/workflows/integration-pr.yaml`: PR check that dispatches the upstream integration workflow.
- `.github/workflows/lint-actions.yaml`: PR lint workflow that runs pre-commit checks.
- `.github/scripts/`: helper scripts used by the workflows for tag/metadata processing.

## Key inputs/outputs (workflow_call)
- Inputs: `WORKDIR`, `TARGETS_JSON`, `IMAGE_TAG`, `TAG_COMMAND`, `CICD_REF`, `RUN_AUTOMATED_UPDATE_ON_PR`, `LATEST_TAG_WORKDIR`.
- Outputs: `changed`, `docker_tag`, `proposed_tag`, `image`, `targets`.

## High-level flow
- Pull requests run `build-only` by default (no updates or publishing).
- Pull requests can run `container-update` instead when
  `RUN_AUTOMATED_UPDATE_ON_PR` is true.
- Same-repo pull requests also dispatch the upstream integration workflow.
- The PR integration workflow creates an ephemeral branch in
  `snw35/cicd-integration`, rewrites
  `.github/workflows/integration-update.yaml` on that branch to pin
  `snw35/cicd/.github/workflows/github.yaml` and
  `snw35/cicd/.github/workflows/create-release.yaml` to the PR head SHA,
  dispatches the integration workflow on that ephemeral branch, and polls until
  completion.
- Scheduled/manual runs (and optional PR automated-update runs):
  - Run `nvchecker` and `dfupdate`.
  - Compute tag metadata, latest-tag ownership, and check for existing tags.
  - Build/test/push images if changes exist or the tag is missing, including
    optional `latest` tagging.
  - Package changes and metadata as artifacts for aggregation.
- Release workflow aggregates per-target patches, commits, and creates a combined tag.

## Workflow decision matrix
For reusable workflows, `github.event_name` reflects the caller event.

| Workflow | Event | Job | If condition | Outputs |
| --- | --- | --- | --- | --- |
| `.github/workflows/github.yaml` | pull_request | build-only | `github.event_name == 'pull_request' && inputs.RUN_AUTOMATED_UPDATE_ON_PR == false` | - |
| `.github/workflows/github.yaml` | schedule, workflow_dispatch, pull_request | container-update | `github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' || (github.event_name == 'pull_request' && inputs.RUN_AUTOMATED_UPDATE_ON_PR)` | - |
| `.github/workflows/github.yaml` | schedule, workflow_dispatch | collect-metadata | `(github.event_name == 'schedule' || github.event_name == 'workflow_dispatch') && needs.container-update.result != 'failure'` | `changed_any`, `docker_tags`, `proposed_tags`, `images`, `targets_json` (feeds workflow outputs) |
| `.github/workflows/create-release.yaml` | workflow_call (any caller event) | aggregate-changes | - | `changed_any`, `docker_tags`, `proposed_tags`, `images`, `targets_json`, `meta_found`, `committed` |
| `.github/workflows/create-release.yaml` | workflow_call (any caller event) | create-release | `needs.aggregate-changes.outputs.changed_any == 'true'` | `tag` (feeds workflow output) |
| `.github/workflows/integration-pr.yaml` | pull_request | integration | `github.event.pull_request.head.repo.full_name == github.repository` | - |
| `.github/workflows/lint-actions.yaml` | pull_request | pre-commit | - | - |

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
  - **Workflows: Read and write**
    - Needed to read and modify `.github/workflows/*`

## Helper scripts
- `dockerfile_base_tag.py`: extracts base image tag from the Dockerfile.
- `dockerfile_envs.py`: reads `ENV` values from the Dockerfile for tagging.
- `latest_tag_owner.py`: decides which target (if any) owns the `latest` tag.
- `collect_updates.py`: merges per-target metadata into workflow outputs.
- `pick_release_tag.py`: computes a combined release tag from changed targets.

## Local troubleshooting (from README)
```
podman run --security-opt label=disable --userns keep-id -it --rm --name nvchecker --mount type=bind,source=${PWD},target=/data/ -w /data snw35/nvchecker:2.9 nvchecker -l debug -c nvchecker.toml

podman run --security-opt label=disable --userns keep-id -it --rm --name dfupdate --mount type=bind,source=${PWD},target=/data/ -w /data snw35/dfupdate:0.2.0
```
