# AI Context: cicd

This repository provides reusable GitHub Actions workflows to automate container
updates using `nvchecker` and `dfupdate`.

## Branches

The primary branch is `main`, and the primary branch that all downstream repositories will use is also `main`.
Feature branches will be named after their purpose, e.g `add-lint-checks` or similar.

## What lives where
- `.github/workflows/container-update.yaml`: shared consumer workflow (workdir matrix, `plan`, legs, release); consumers carry only a thin caller.
- `.github/workflows/github.yaml`: reusable workflow for one leg: build, update, tag, and publish.
- `.github/workflows/create-release.yaml`: aggregates per-target updates, commits, and creates releases.
- `.github/workflows/integration-pr.yaml`: PR check that dispatches the upstream integration workflow.
- `.github/workflows/lint-actions.yaml`: PR lint workflow that runs pre-commit checks.
- `.github/scripts/`: helper scripts used by the workflows for tag/metadata processing (`test_scripts.py`: `python3 -m unittest` there).
- `.github/actionlint.yaml`: ignores actionlint's rejection of the `$/` reusable-workflow form.

## Key inputs (workflow_call)
- `container-update.yaml`: `WORKDIRS` (JSON array), `IMAGE_TAG`, `IMAGE_TAG_BY_WORKDIR`, `DATE_VERSION`, `LATEST_TAG_WORKDIR`, `RUN_AUTOMATED_UPDATE_ON_PR`, `CICD_REF`.
- `github.yaml` (one leg): `WORKDIR`, `IMAGE_TAG`, `CICD_REF`, `RUN_AUTOMATED_UPDATE_ON_PR`, `LATEST_TAG_WORKDIR`, `TIP_SHA`, `WORKDIRS`, `DATE_VERSION`, `RUN_DATE`. No outputs.
- `create-release.yaml`: `CICD_REF`, `expected_workdirs`; output `tag`.

## High-level flow
- Pull requests run `build-only` by default (no updates or publishing).
- Pull requests can run `container-update` instead when
  `RUN_AUTOMATED_UPDATE_ON_PR` is true.
- Same-repo pull requests also dispatch the upstream integration workflow.
- The PR integration workflow creates an ephemeral branch in
  `snw35/cicd-integration`, rewrites
  `.github/workflows/integration-update.yaml` on that branch to pin
  `snw35/cicd/.github/workflows/container-update.yaml` to the PR head SHA
  (nested `$/` calls follow it), dispatches the integration workflow on that
  ephemeral branch, and polls until completion. The `release` job only runs on a
  default branch, so this check does not execute `create-release.yaml`.
- Scheduled/manual runs (and optional PR automated-update runs), per leg:
  - Run `nvchecker` and `dfupdate`.
  - Compute the image tag `[workdir-]<main version>` and latest-tag ownership; compare the published image's revision label with the leg's changed paths.
  - Build/test/push the (moving) tag if changes exist, the published image is stale or missing,
    or the leg's files changed since the commit the published image was built from; optional `latest` tagging.
  - Package changes and metadata as artifacts for aggregation.
- Push to the default branch: same, minus nvchecker/dfupdate (builds the committed Dockerfile at the planned tip).
- The release job aggregates per-target patches, commits, and creates a combined tag + release when a main version changed, else refreshes the existing release body.

## Workflow decision matrix
For reusable workflows, `github.event_name` reflects the caller event.

| Workflow | Event | Job | If condition | Outputs |
| --- | --- | --- | --- | --- |
| `.github/workflows/container-update.yaml` | non-PR | plan | not a push to a non-default branch | `tip_sha` |
| `.github/workflows/container-update.yaml` | any | update-images | `!cancelled() && needs.plan.result != 'failure'` | - |
| `.github/workflows/container-update.yaml` | non-PR, default branch | release | `!cancelled() && event != pull_request && ref is default branch && needs.update-images.result != 'skipped'` | `tag` |
| `.github/workflows/github.yaml` | pull_request | build-only | `github.event_name == 'pull_request' && inputs.RUN_AUTOMATED_UPDATE_ON_PR == false` | - |
| `.github/workflows/github.yaml` | schedule, workflow_dispatch, push (default branch), pull_request | container-update | schedule/dispatch, or push to the default branch, or pull_request with `RUN_AUTOMATED_UPDATE_ON_PR` | - |
| `.github/workflows/create-release.yaml` | workflow_call | aggregate-changes | - | `tag` |
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
- `dockerfile_envs.py`: reads `ENV` values from the Dockerfile; `alias` builds the image tag, `versions` lists versions for the release body.
- `latest_tag_owner.py`: decides which target (if any) owns the `latest` tag.
- `collect_updates.py`: merges per-target metadata, computes release names and the `release_needed` decision.
- `select_legs.py`: resolves the tip once and `stale` decides per leg whether the published image predates changes to the leg's files.

## Local troubleshooting (from README)
```
podman run --security-opt label=disable --userns keep-id -it --rm --name nvchecker --mount type=bind,source=${PWD},target=/data/ -w /data snw35/nvchecker:2.20 nvchecker -l debug -c nvchecker.toml

podman run --security-opt label=disable --userns keep-id -it --rm --name dfupdate --mount type=bind,source=${PWD},target=/data/ -w /data snw35/dfupdate:2.2.2
```
