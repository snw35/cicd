#!/usr/bin/env python3
import glob
import json
import os
import sys


def main() -> int:
    updates_dir = os.environ.get("UPDATES_DIR", "/tmp/updates")
    metas = glob.glob(os.path.join(updates_dir, "*-meta.json"))
    targets = []
    for meta_file in metas:
        with open(meta_file, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
        meta["changed"] = str(meta.get("changed", "false")).lower() == "true"
        meta["tag_exists"] = str(meta.get("tag_exists", "false")).lower() == "true"
        targets.append(meta)

    changed_any = any(t["changed"] or not t["tag_exists"] for t in targets)
    docker_tags = {t.get("name"): t.get("docker_tag", "") for t in targets}
    proposed_tags = {t.get("name"): t.get("proposed_tag", "") for t in targets}
    images = {t.get("name"): t.get("image", "") for t in targets}
    tags_to_create = [
        t.get("proposed_tag")
        for t in targets
        if t.get("proposed_tag") and not t["tag_exists"]
    ]

    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        print("GITHUB_OUTPUT not set", file=sys.stderr)
        return 1

    with open(output, "a", encoding="utf-8") as handle:
        handle.write(f"meta_found={str(len(targets) > 0).lower()}\n")
        handle.write(f"changed_any={str(changed_any).lower()}\n")
        handle.write(f"targets_json={json.dumps(targets)}\n")
        handle.write(f"docker_tags={json.dumps(docker_tags)}\n")
        handle.write(f"proposed_tags={json.dumps(proposed_tags)}\n")
        handle.write(f"images={json.dumps(images)}\n")
        handle.write(f"tags_to_create={len(tags_to_create)}\n")
        handle.write(f"tag_names={json.dumps(tags_to_create)}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
