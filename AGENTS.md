# AI Context: cicd

This repository provides reusable GitHub Actions workflows to automate container
updates using `nvchecker` and `dfupdate`.

## What lives where
- `.github/workflows/github.yaml`: reusable workflow for build, update, tag, and publish.
- `.github/workflows/create-release.yaml`: aggregates per-target updates and creates releases.
- `.github/scripts/`: helper scripts used by the workflows for tag/metadata processing.
- `integration-test/`: sample Dockerfile and nvchecker config for testing.

## Key inputs/outputs (workflow_call)
- Inputs: `WORKDIR`, `TARGETS_JSON`, `IMAGE_TAG`, `TAG_COMMAND`, `CICD_REF`.
- Outputs: `changed`, `docker_tag`, `proposed_tag`, `image`, `targets`.

## High-level flow
- Pull requests only build a container image (no updates or publishing).
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
| `.github/workflows/lint-actions.yaml` | pull_request | actionlint | - | - |

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
