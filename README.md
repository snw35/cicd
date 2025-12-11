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
    if: github.ref_name == github.event.repository.default_branch && contains(toJson(needs.*.outputs.changed), 'true')
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Pick release tag from changed matrix job
        id: pick_tag
        run: |
          needs_json='${{ toJson(needs) }}'
          tag="$(python3 - <<'PY' "$needs_json"
import json, sys
needs = json.loads(sys.argv[1])
tags = [job["outputs"]["docker_tag"] for job in needs.values() if job["outputs"].get("changed") == "true"]
if not tags:
    sys.exit("No changed matrix jobs found")
print(tags[0])
PY
)"
          echo "tag=$tag" >> "$GITHUB_OUTPUT"
      - uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ steps.pick_tag.outputs.tag }}
          name: Release ${{ steps.pick_tag.outputs.tag }}
          body: Automated release for ${{ steps.pick_tag.outputs.tag }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Which will process:

 * repo/web/Dockerfile
 * repo/backend/Dockerfile

The default is to run for the current working directory only. Each matrix job emits `changed` and `docker_tag` outputs; the aggregator job above inspects those outputs and creates a single GitHub release if any Dockerfile changed.
