# cicd

Continuous Integration and Continuous Deployment Scripts.

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
