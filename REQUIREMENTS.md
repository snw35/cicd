# Requirements: cicd workflows

These requirements describe behaviors that must be preserved when modifying the
workflows or helper scripts.

## Workflow triggers and scope
- The reusable workflow remains `workflow_call`-driven and preserves its outputs.
- `build-only` runs only on `pull_request` events and only builds an image.
- `container-update` runs only on `schedule` or `workflow_dispatch` events.
- `create-release` only runs when at least one target changed or a tag is missing.

## CICD helper resolution (must respect CICD_REF)
- If `CICD_REF` input is set, it is always used for helper script checkout.
- If `CICD_REF` is unset:
  - Prefer the `github.workflow_ref` ref when present.
  - If running within `snw35/cicd`, fall back to `GITHUB_REF_NAME`.
  - Otherwise default to `main`.
- If running in `snw35/cicd` and `.github/scripts` exists, use local scripts.
- Otherwise checkout `snw35/cicd` into `.cicd` at the resolved ref.

## Tagging and change detection
- Changes are detected via `git status` in the repo workspace.
- Tags are checked on the remote via `git ls-remote --tags` using `GH_TOKEN`.
- `PROPOSED_TAG` is computed as:
  - `${ENV_VERSIONS}-${BASE_VERSION}` for `WORKDIR == '.'`
  - `${WORKDIR}-${ENV_VERSIONS}-${BASE_VERSION}` otherwise.
- `DOCKER_TAG` is computed in this order:
  1) `TAG_COMMAND` output (prefixed by `WORKDIR` when not `.`)
  2) `IMAGE_TAG` value from Dockerfile `ENV` (prefixed by `WORKDIR` when not `.`)
  3) `PROPOSED_TAG`
- Images are built/tested/pushed only when changes exist or the tag is missing.

## Artifacts and outputs
- Per-target artifacts include:
  - `/tmp/<target-slug>-changes.patch` when there are staged changes.
  - `/tmp/<target-slug>-meta.json` with keys: `name`, `workdir`, `changed`,
    `tag_exists`, `proposed_tag`, `docker_tag`, `image`.
- Artifact names follow `update-<target-slug>-<run-attempt>`.
- `collect_updates.py` is the source of truth for output shapes and must stay in sync.

## Release aggregation
- Aggregation applies all per-target patches before commit.
- Commit message stays `Automated container updates`.
- Release tags combine per-target tags in stable order and use `docker_tag` or
  `proposed_tag` when a tag is missing.

## Operational invariants (checklist)
- Per-target artifacts are uploaded for every `container-update` run; `/tmp/<target-slug>-meta.json` must always exist.
- `/tmp/<target-slug>-changes.patch` is created only when staged changes exist after the packaging step.
- Images are built/tested/pushed only when `CHANGED == 'true'` or `TAG_EXISTS == 'false'`.
- Aggregation applies patches only when `collect_updates.py` reports `meta_found == 'true'`.
- Commits are created only when `meta_found == 'true'` and the workspace is dirty; message stays `Automated container updates`.
- Release tag push and GitHub release only occur when `steps.pick_tag.outputs.tag` is non-empty and `changed_any == 'true'`.
