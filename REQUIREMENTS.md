# Requirements: cicd workflows

These requirements describe behaviors that must be preserved when modifying the
workflows or helper scripts.

## Workflow triggers and scope
- Consumers call `container-update.yaml` (workdir matrix, `plan`, legs, release) from a thin caller; `github.yaml` (one leg) and `create-release.yaml` are its nested `$/` calls and run from the same commit.
- `build-only` runs on `pull_request` when `RUN_AUTOMATED_UPDATE_ON_PR` is `false`, and only builds an image.
- `container-update` (a leg) runs in `update` mode on `schedule`/`workflow_dispatch` (and on `pull_request` when `RUN_AUTOMATED_UPDATE_ON_PR` is `true`) and in `publish` mode on `push` to the default branch. `publish` mode skips nvchecker/dfupdate and builds the committed Dockerfile as-is at the tip resolved once by `plan`. Pushes to other branches run nothing.
- `plan` runs for every non-PR event on a default branch; a failed `plan` stops the legs.
- `release` (create-release.yaml) runs after the legs on every non-PR default-branch run (`!cancelled()`), and fails the run when a leg produced no image.

## CICD helper resolution (must respect CICD_REF)
- If `CICD_REF` input is set, it is used for helper script checkout.
- If `CICD_REF` is unset, current fallback order is job-specific and must be preserved:
  - In `.github/workflows/github.yaml` jobs, prefer `github.workflow_ref`, then use `GITHUB_REF_NAME` when running in `snw35/cicd`, else default to `main`.
  - In `.github/workflows/create-release.yaml` `aggregate-changes`, prefer `GITHUB_REF_NAME` when running in `snw35/cicd`, then `github.workflow_ref`, else `main`.
  - In `container-update.yaml` `plan`, the `CICD_REF` input is always used (checkout of `snw35/cicd` into `.cicd`).
- If running in `snw35/cicd` and `.github/scripts` exists, use local scripts.
- Otherwise checkout `snw35/cicd` into `.cicd` at the resolved ref.

## Tagging and change detection
- Changes are detected via `git status` in the repo workspace (update mode); `CHANGED=false` in publish mode.
- `IMAGE_TAG` is the Dockerfile `ENV` naming the main software. `dockerfile_envs.py alias` gives the image tag `[<workdir>-]<main version>` (no tag built from other versions); characters illegal in a tag and spaces become `-`, and the result is validated (a folder name must be tag-safe). `versions` lists the `*_VERSION` values and the base tag as JSON (release body only).
- Image tags move: a leg re-pushes `[<workdir>-]<main version>` (Docker Hub and ghcr; folder/`latest` tags first, the moving tag last) whenever it publishes; the digest identifies an exact build. Builds carry the label `org.opencontainers.image.revision` (the checked-out HEAD) and `.source`.
- `IMAGE_STALE` = on either registry the tag is missing, its revision label is absent/not an ancestor of HEAD, or `select_legs.py stale` finds non-bot, non-ignored paths changed in `<label>..HEAD` that select this leg (owned/shared rules over the caller's `WORKDIRS`; bot commits `Automated container updates` excluded). The label is parsed by `image_label.py` (single manifest or platform map). "Manifest unknown" ⇒ stale, any other error fails the leg. In update mode the label is the pre-bot checkout, so at worst one extra rebuild. `PUBLISH = CHANGED || IMAGE_STALE`. Images are built/tested/pushed only when `PUBLISH` is true. Docker Hub and ghcr logins are not gated.
- `plan` (`select_legs.py`) resolves the tip once (`TIP_SHA`); publish-mode legs build exactly that commit. No run-history lookup exists.
- `DATE_VERSION` (opt-in): the `IMAGE_TAG` ENV occurs exactly once and holds `YYYY-MM-DD[-N]` (N ≥ 2 optional; validated in every mode). In update mode, after dfupdate, `date_version.py` rewrites it when the Dockerfile differs from HEAD: an older date becomes `RUN_DATE` (resolved once by `plan`, UTC; fallback `date -u`), the same or a later date gets `-(N+1)`; a tag already on Docker Hub is skipped by incrementing. Publish mode never bumps.
- `latest_tag_owner.py` determines whether the current target receives `latest` using `WORKDIR` and optional `LATEST_TAG_WORKDIR`.
- Root `docker-compose.yaml` validation is attempted before push when `PUBLISH` is true, and is skipped when absent or when GPU requirements are detected.

## Artifacts and outputs
- Per-target artifacts include:
  - `/tmp/<target-slug>-changes.patch` when there are staged changes.
  - `/tmp/<target-slug>-meta.json` with keys: `name`, `workdir`, `mode`, `changed`, `published`, `alias` (the image tag), `digest`, `versions`, `image`, `ghcr_image`, `tip_sha`.
- Artifact names follow `update-<target-slug>-<run_id>`.
- `collect_updates.py` is the source of truth for output shapes and must stay in sync.

## Release aggregation
- Aggregation applies all per-target patches before commit.
- Commit message stays `Automated container updates` (`select_legs.py` ignores such commits when computing changed paths).
- The release/tag name is computed from all legs sorted by `workdir`: `combined_tag` = join of the legs' image tags (main versions only).
- `release_needed = tag_missing && no blocking leg`; `tag_missing` is a `git ls-remote --tags` lookup of `combined_tag` (i.e. a main version changed). A leg listed in `expected_workdirs` without metadata blocks; a blocked run creates/edits nothing and fails the job. A dependency- or base-only bump finds the tag and only refreshes the existing release body (when a leg published and the deterministic body, which ends in a `cicd-state-sha` marker, differs and is not older than the marker); a tag without a release gets the release created.
- The tag is created at the release commit (HEAD after the bot commit push, else the legs' common `tip_sha`) without force; an existing tag at or before the branch is left alone; any other existing tag fails. No tag is ever moved.

## Operational invariants (checklist)
- Per-target artifacts are uploaded for every `container-update` leg; `/tmp/<target-slug>-meta.json` must always exist.
- Artifacts are named `update-<target-slug>-<run_id>` (not `run_attempt`) so "re-run failed jobs" still finds earlier attempts' artifacts; collectors do not use `continue-on-error`, and `collect_updates.py` fails when no metadata is found.
- `/tmp/<target-slug>-changes.patch` is created only when `CHANGED == 'true'` and staged changes exist after the packaging step.
- Images are built/tested/pushed only when `PUBLISH == 'true'`.
- Commits are created only when the workspace is dirty after applying patches; message stays `Automated container updates`.
- The release tag and GitHub release are created only when `release_needed == 'true'`; a git tag is never moved; the release body is edited with `gh release edit`, which leaves assets alone.
- `release` is gated with `!cancelled()` and is safe only because `expected_workdirs` blocking is in the same `create-release.yaml`; keep them together.

## Coding Style
- Prefer implementing reusable logic in scripts under `.github/scripts/`.
- Inline shell and `actions/github-script` are used in workflows for orchestration; keep these steps focused and readable.
- Before creating a new script, examine existing scripts and extend their logic when appropriate.
- Prefer clear job separation and explicit step conditions over deeply nested conditional logic.
