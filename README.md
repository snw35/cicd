# cicd

Continuous Integration and Continuous Deployment Scripts.

This reusable GitHub Actions workflow is designed to enable fully-automated container updates. It uses the following two containers to do this:

  * https://github.com/snw35/nvchecker
  * https://github.com/snw35/dfupdate

Both containers are also udated by this workflow, and therefore by themselves. The [ReadMe for dfupdate](https://github.com/snw35/dfupdate) explains how to set a repository up to use it.

For AI coding assistants, see `AGENTS.md` (repo context) and `REQUIREMENTS.md` (behavioral constraints).

## PR integration checks

Pull requests in this repo dispatch the upstream integration workflow in
`snw35/cicd-integration` and wait for completion.

`integration-pr.yaml` creates an ephemeral branch in `snw35/cicd-integration`,
rewrites `.github/workflows/integration-update.yaml` on that branch to use the
PR commit SHA for the `container-update.yaml` reference (its nested workflow calls
use `$/` and follow that commit), dispatches `integration-update.yaml` on that
branch, and then polls the dispatched run. The release job only runs on a default
branch, so this check does not execute `create-release.yaml`.

Required secret in this repo:

- `CICD_INTEGRATION_TOKEN`: fine-grained PAT scoped to repository
  `snw35/cicd-integration` with least-privilege permissions:
  - **Actions: Read and write** (required to create workflow dispatch; also
    covers polling/listing runs).
  - **Contents: Read and write** (required to read default-branch workflow
    content, create/update the ephemeral branch ref, and commit rewritten
    workflow content).
  - **Workflows: Read and write** (required to read and modify the contents
    of `.github/workflows` when patching the MR ref into the workflow dispatch).

- `snw35/cicd-integration/.github/workflows/integration-update.yaml` to accept a
  `cicd_ref` input and pass it through to the reusable workflow calls.

Minimal upstream adjustment:

```yaml
on:
  workflow_dispatch:
    inputs:
      cicd_ref:
        required: false
...
with:
  CICD_REF: ${{ inputs.cicd_ref || vars.CICD_REF || 'main' }}
```

## Troubleshooting Steps

The container update steps can be run locally on Fedora with:

```
podman run --security-opt label=disable --userns keep-id -it --rm --name nvchecker --mount type=bind,source=${PWD},target=/data/ -w /data snw35/nvchecker:2.20 nvchecker -l debug -c nvchecker.toml

podman run --security-opt label=disable --userns keep-id -it --rm --name dfupdate --mount type=bind,source=${PWD},target=/data/ -w /data snw35/dfupdate:2.2.2
```

The Github Actions linter can be run locally on Fedora with:

```
podman run --security-opt label=disable --userns keep-id --rm -v $(pwd):/repo --workdir /repo rhysd/actionlint:latest -color
```

For lint-only checks without Docker, use pre-commit:

```
pre-commit install
pre-commit run --all-files
```

## Consumer setup

A repository that wants automated updates carries one thin workflow that calls the shared workflow:

```yaml
name: Docker Image CI

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]
  schedule:
    - cron: '05 15 * * 0'
  workflow_dispatch:

jobs:
  container-update:
    concurrency:
      group: ${{ github.event_name == 'pull_request' && format('pr-{0}', github.run_id) || format('container-update-{0}', github.repository) }}
      queue: max
      cancel-in-progress: false
    permissions:
      contents: write
      packages: write
    uses: snw35/cicd/.github/workflows/container-update.yaml@main
    with:
      WORKDIRS: '["web","backend"]'   # one entry per Dockerfile folder; '["."]' for a root Dockerfile
      IMAGE_TAG: CONFD_VERSION        # Dockerfile ENV holding the main software version
      # DATE_VERSION: true            # optional, for images bundling many packages with no single main one:
      #                               # IMAGE_TAG then names an ENV holding a date, e.g. `ENV MYENV_VERSION 2026-10-04`
    secrets: inherit
```

Which will process:

 * repo/web/Dockerfile
 * repo/backend/Dockerfile

Optional inputs: `DATE_VERSION` (see below), `IMAGE_TAG_BY_WORKDIR` (JSON map overriding `IMAGE_TAG` per workdir), `LATEST_TAG_WORKDIR`, `RUN_AUTOMATED_UPDATE_ON_PR`, `CICD_REF` (helper scripts ref, defaults to `main`). `queue: max` keeps every waiting run instead of replacing the older one; actionlint may need an ignore for it (see `.github/actionlint.yaml` in the consumer repos).

Tags per Dockerfile: one image tag `<workdir>-<main version>` (no workdir prefix for `.`; characters illegal in a tag become `-`), plus the plain `<workdir>` tag for workdirs. The tag names the main software only: when the base image or a dependency changes the same tag is rebuilt and re-pushed, and the digest identifies an exact build. A git tag and GitHub release, named by the image tags of all workdirs joined in workdir order (for example `web-1.0-backend-2.1`), are created only when a main version changes; dependency- or base-only bumps update the existing release body (versions, digests) and create nothing new. A push to the default branch re-publishes the committed Dockerfile as-is (no nvchecker/dfupdate) for the workdirs whose files changed or whose published image is stale. Repos that build several variants use one folder per variant; the folder prefix is the variant marker.

Date versions (`DATE_VERSION: true`): for "package" style images (for example a devcontainer or a cloud-tools image) with many equal-weight packages and no single main one. Add `ENV MYENV_VERSION 2026-10-04` once to the Dockerfile (use the date of the newest existing release; optionally `ENV MYENV_UPGRADE false` so dfupdate skips it explicitly) and set `IMAGE_TAG: MYENV_VERSION`. The ENV must occur once and be `YYYY-MM-DD` or `YYYY-MM-DD-N`, otherwise the run fails. When an update run changes the Dockerfile (a dependency or the base image), the ENV is rewritten to the run's UTC date before the build (the same date again becomes `-2`, `-3`, ...; an older or already-published tag is never reused), and the bot commit carries it. The image tag is then the date, and every new date is a new main version: new git tag and release, the tag never moves. Re-runs and hand fixes leave the ENV alone, so they keep the tag and refresh the existing release body; edit the date by hand to start a new release.

Helper scripts are resolved from `snw35/cicd` and checked out to `.cicd` automatically when running from downstream repositories.
