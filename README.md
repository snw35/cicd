# cicd

Continuous Integration and Continuous Deployment Scripts.

This reusable GitHub Actions workflow is designed to enable fully-automated container updates. It uses the following two containers to do this:

  * https://github.com/snw35/nvchecker
  * https://github.com/snw35/dfupdate

Both containers are also udated by this workflow, and by themselves.

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

## Using the reusable workflow for multiple Dockerfiles

The reusable workflow accepts a `WORKDIR` input so you can run it against Dockerfiles in subdirectories. From a downstream repository you can fan out over multiple services with a matrix, for example:

```yaml
jobs:
  update-images:
    strategy:
      matrix:
        workdir: [web, backend]
    uses: snw35/cicd/.github/workflows/github.yaml@dockerfile-parse
    with:
      WORKDIR: ${{ matrix.workdir }}
      IMAGE_TAG: CONFD_VERSION
    secrets: inherit
```

Which will process:

 * repo/web/Dockerfile
 * repo/backend/Dockerfile

The default is to run for the current working directory only.
