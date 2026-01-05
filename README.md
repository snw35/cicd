# cicd

Continuous Integration and Continuous Deployment Scripts.

This reusable GitHub Actions workflow is designed to enable fully-automated container updates. It uses the following two containers to do this:

  * https://github.com/snw35/nvchecker
  * https://github.com/snw35/dfupdate

Both containers are also udated by this workflow, and therefore by themselves. The [ReadMe for dfupdate](https://github.com/snw35/dfupdate) explains how to set a repository up to use it.

## Troubleshooting Steps

The container update steps can be run locally on Fedora with:

```
podman run --security-opt label=disable --userns keep-id -it --rm --name nvchecker --mount type=bind,source=${PWD},target=/data/ -w /data snw35/nvchecker:2.9 nvchecker -l debug -c nvchecker.toml

podman run --security-opt label=disable --userns keep-id -it --rm --name dfupdate --mount type=bind,source=${PWD},target=/data/ -w /data snw35/dfupdate:0.2.0
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

## Multiple Dockerfiles

The reusable workflow accepts a `WORKDIR` input so you can run it against Dockerfiles in subdirectories. From a downstream repository you can fan out over multiple services with a matrix, for example:

```yaml
jobs:
  update-images:
    strategy:
      matrix:
        workdir: [web, backend]
    uses: snw35/cicd/.github/workflows/github.yaml@mainline
    with:
      WORKDIR: ${{ matrix.workdir }}
      IMAGE_TAG: CONFD_VERSION
    secrets: inherit

  create-release:
    needs: update-images
    if: github.ref_name == github.event.repository.default_branch && needs.update-images.outputs.changed == 'true'
    uses: snw35/cicd/.github/workflows/create-release.yaml@mainline
    secrets: inherit
```

Which will process:

 * repo/web/Dockerfile
 * repo/backend/Dockerfile

Helper scripts are resolved from the reusable workflow ref (via `GITHUB_WORKFLOW_REF`) and checked out to `.cicd` automatically.

The default is to run for the current working directory only. Each matrix run emits `changed` (aggregated across targets), `docker_tag`, `proposed_tag`, `image`, and `targets` outputs. The downstream `create-release` workflow collects the per-target artifacts produced by the updater, applies the combined patch, and creates a single release if any Dockerfile changed. If multiple Dockerfiles were updated, the release tag and name will combine each updated workdir and tag (for example `web-1.0-backend-1.0`).
