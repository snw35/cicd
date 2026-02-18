# Requirements: cicd workflows

These requirements describe behaviors that must be preserved when modifying the
workflows or helper scripts.

## Workflow triggers and scope
- The reusable workflow remains `workflow_call`-driven and preserves its outputs.
- `build-only` runs on `pull_request` when `RUN_AUTOMATED_UPDATE_ON_PR` is `false`, and only builds an image.
- `container-update` runs on `schedule` and `workflow_dispatch`, and can also run on `pull_request` when `RUN_AUTOMATED_UPDATE_ON_PR` is `true`.
- `collect-metadata` runs only for `schedule`/`workflow_dispatch` when `container-update` does not fail.
- `create-release` runs only when aggregated `changed_any == 'true'`.

## CICD helper resolution (must respect CICD_REF)
- If `CICD_REF` input is set, it is used for helper script checkout.
- If `CICD_REF` is unset, current fallback order is job-specific and must be preserved:
  - In `.github/workflows/github.yaml` jobs, prefer `github.workflow_ref`, then use `GITHUB_REF_NAME` when running in `snw35/cicd`, else default to `main`.
  - In `.github/workflows/create-release.yaml` `aggregate-changes`, prefer `GITHUB_REF_NAME` when running in `snw35/cicd`, then `github.workflow_ref`, else `main`.
  - In `.github/workflows/create-release.yaml` `create-release`, prefer `GITHUB_REF_NAME` when running in `snw35/cicd`, else `main`.
- If running in `snw35/cicd` and `.github/scripts` exists, use local scripts.
- Otherwise checkout `snw35/cicd` into `.cicd` at the resolved ref.

## Tagging and change detection
- Changes are detected via `git status` in the repo workspace.
- Tags are checked on the remote via `git ls-remote --tags` using `GH_TOKEN`.
- `latest_tag_owner.py` determines whether the current target receives `latest` using `TARGETS_JSON`, `WORKDIR`, and optional `LATEST_TAG_WORKDIR`.
- `PROPOSED_TAG` is computed as:
  - `${ENV_VERSIONS}-${BASE_VERSION}` for `WORKDIR == '.'`
  - `${WORKDIR}-${ENV_VERSIONS}-${BASE_VERSION}` otherwise.
- `DOCKER_TAG` is computed in this order:
  1) `TAG_COMMAND` output (prefixed by `WORKDIR` when not `.`)
  2) `IMAGE_TAG` value from Dockerfile `ENV` (prefixed by `WORKDIR` when not `.`)
  3) `PROPOSED_TAG`
- Images are built/tested/pushed only when changes exist or the tag is missing.
- Root `docker-compose.yaml` validation is attempted before push when build/push conditions are met, and is skipped when absent or when GPU requirements are detected.

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
- Release tags combine per-target tags in stable order (sorted by `workdir`, then `name`) and use `docker_tag` or `proposed_tag` when a tag is missing.

## Operational invariants (checklist)
- Per-target artifacts are uploaded for every `container-update` run; `/tmp/<target-slug>-meta.json` must always exist.
- `/tmp/<target-slug>-changes.patch` is created only when staged changes exist after the packaging step.
- Images are built/tested/pushed only when `CHANGED == 'true'` or `TAG_EXISTS == 'false'`.
- Aggregation applies patches only when `collect_updates.py` reports `meta_found == 'true'`.
- Commits are created only when `meta_found == 'true'` and the workspace is dirty; message stays `Automated container updates`.
- Release tag push and GitHub release only occur when `steps.pick_tag.outputs.tag` is non-empty and `changed_any == 'true'`.

## Coding Style
- Prefer implementing reusable logic in scripts under `.github/scripts/`.
- Inline shell and `actions/github-script` are used in workflows for orchestration; keep these steps focused and readable.
- Before creating a new script, examine existing scripts and extend their logic when appropriate.
- Prefer clear job separation and explicit step conditions over deeply nested conditional logic.
