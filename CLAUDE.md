# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository context

Read these two files — they are the authoritative context and spec for this repo:

@AGENTS.md
@REQUIREMENTS.md

`REQUIREMENTS.md` is a behavioural contract, not documentation. Check any change to
`.github/workflows/` or `.github/scripts/` against its "Operational invariants" checklist
before considering the change done.

## Verification

There is no build and no in-repo test suite. Verify changes with:

```
pre-commit install       # first time only
pre-commit run --all-files
```

Real end-to-end testing happens off-repo: `integration-pr.yaml` dispatches
`snw35/cicd-integration`, so a green pre-commit run is not proof the workflows work.

## Style

- Python helpers have **no** `ruff.toml`/`pyproject.toml` — ruff runs on pure defaults
  (88 columns, double quotes). Do not add a config file to work around a lint failure.
- Helper scripts are stdlib-only apart from `dockerfile-parse`, which CI installs with
  `pip3 install dockerfile-parse --break-system-packages`. There is no requirements file;
  adding a third-party dependency means editing the workflow.
- Tool versions are pinned in `.pre-commit-config.yaml` and in `env:` at the top of
  `.github/workflows/github.yaml`. Keep the README's podman troubleshooting snippets in
  sync with those `env:` pins.

## Gotchas

- The `CICD_REF` fallback order **differs per job** and is deliberate — see the
  "CICD helper resolution" section of `REQUIREMENTS.md`. It has regressed before. Do not
  "normalise" the three variants into one.
- `collect_updates.py` is the source of truth for artifact/output shapes. Changing an
  output means changing that script and every consumer together.
- Change detection is `git status --porcelain` over the whole workspace, not per-`WORKDIR`.
- `integration-pr.yaml` runs only for same-repo PRs, so forks never exercise integration.

## Repo etiquette

- Branch off `main`. Branch names are short kebab-case purpose descriptors with no prefix
  (`ghcr`, `run-on-pr`, `compose-test`).
- Commit subjects are short, capitalised, imperative, with no body and no
  conventional-commit prefix (`Add compose validate step`).
- Everything lands via a GitHub PR merge commit; nothing is pushed directly to `main`.
