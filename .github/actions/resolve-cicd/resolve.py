#!/usr/bin/env python3
import os
import sys


def parse_workflow_ref(workflow_ref: str) -> tuple[str, str]:
    if not workflow_ref:
        return "", ""
    before, sep, ref = workflow_ref.partition("@")
    repo = before
    marker = "/.github/workflows/"
    if marker in before:
        repo = before.split(marker, 1)[0]
    return repo, ref if sep else ""


def first_existing(paths: list[tuple[str, str]]) -> tuple[str, str]:
    for repo_dir, scripts_dir in paths:
        if scripts_dir and os.path.isdir(scripts_dir):
            return repo_dir, scripts_dir
    return "", ""


def write_kv(path: str, data: dict[str, str]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in data.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    input_repo = os.environ.get("INPUT_CICD_REPO", "").strip()
    input_ref = os.environ.get("INPUT_CICD_REF", "").strip()
    workflow_ref = os.environ.get("WORKFLOW_REF", "").strip()
    action_repo = os.environ.get("ACTION_REPO", "").strip()
    action_ref = os.environ.get("ACTION_REF", "").strip()
    action_path = os.environ.get("ACTION_PATH", "").strip()
    github_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    github_ref_name = os.environ.get("GITHUB_REF_NAME", "").strip()
    workspace = os.environ.get("GITHUB_WORKSPACE", "").strip()

    wf_repo, wf_ref = parse_workflow_ref(workflow_ref)

    repo = input_repo or action_repo or wf_repo or "snw35/cicd"
    ref = input_ref
    if not ref:
        if action_ref and repo == action_repo:
            ref = action_ref
        elif wf_ref and repo == wf_repo:
            ref = wf_ref
        elif repo == github_repo and github_ref_name:
            ref = github_ref_name
        else:
            ref = "mainline"

    action_repo_dir = ""
    action_scripts_dir = ""
    if action_path:
        action_repo_dir = os.path.abspath(
            os.path.join(action_path, os.pardir, os.pardir, os.pardir)
        )
        action_scripts_dir = os.path.join(action_repo_dir, ".github", "scripts")

    use_action_repo = False
    if action_scripts_dir and os.path.isdir(action_scripts_dir):
        if action_repo and repo == action_repo:
            use_action_repo = True
        elif not action_repo and repo == "snw35/cicd":
            use_action_repo = True

    repo_dir = ""
    scripts_dir = ""
    need_checkout = True

    if use_action_repo:
        repo_dir = action_repo_dir
        scripts_dir = action_scripts_dir
        need_checkout = False
    elif repo == github_repo:
        candidates = []
        if workspace:
            candidates.append((workspace, os.path.join(workspace, ".github", "scripts")))
        candidates.append(("/github/workspace", "/github/workspace/.github/scripts"))
        candidates.append((os.getcwd(), os.path.join(os.getcwd(), ".github", "scripts")))
        repo_dir, scripts_dir = first_existing(candidates)
        if scripts_dir:
            need_checkout = False

    if need_checkout:
        repo_dir = os.path.join(workspace or ".", ".cicd")
        scripts_dir = os.path.join(repo_dir, ".github", "scripts")

    env_path = os.environ.get("GITHUB_ENV", "")
    out_path = os.environ.get("GITHUB_OUTPUT", "")
    if not env_path or not out_path:
        print("GITHUB_ENV or GITHUB_OUTPUT not set", file=sys.stderr)
        return 1

    values = {
        "CICD_REPO": repo,
        "CICD_REF": ref,
        "CICD_REPO_DIR": repo_dir,
        "CICD_SCRIPTS_DIR": scripts_dir,
        "CICD_NEED_CHECKOUT": "true" if need_checkout else "false",
    }
    write_kv(env_path, values)
    outputs = {
        "cicd_repo": repo,
        "cicd_ref": ref,
        "cicd_repo_dir": repo_dir,
        "cicd_scripts_dir": scripts_dir,
        "cicd_need_checkout": "true" if need_checkout else "false",
    }
    write_kv(out_path, outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
