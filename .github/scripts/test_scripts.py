"""Unit tests for the helper scripts (stdlib unittest; `python3 -m unittest`
from this directory; dockerfile-parse must be installed)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

import collect_updates as cu
import date_version as dv
import dockerfile_envs as de
import image_label as il
import select_legs as sl


def write_dockerfile(text: str) -> str:
    handle = tempfile.NamedTemporaryFile("w", suffix=".Dockerfile", delete=False)
    handle.write(text)
    handle.close()
    return handle.name


DFUPDATE = """FROM python:3.14.7-alpine3.24
ENV DFUPDATE_VERSION 2.2.2
ENV REQUESTS_VERSION 2.34.2
ENV TENACITY_VERSION 9.1.4
ENV DOCKERFILE_PARSE_VERSION 2.0.1
"""

SAW = """FROM nvidia/cuda:12.9.2-cudnn-devel-ubuntu24.04
ENV UV_VERSION 0.12.19
ENV SAGE_VERSION 2.2.0
"""


GHRUNNER = """FROM nvidia/cuda:13.0.3-base-ubuntu24.04
ENV DEBIAN_FRONTEND=noninteractive
ENV GHRUNNER_VERSION=2.337.0
ENV GHRUNNER_URL=https://github.com/actions/runner/releases/download/v${GHRUNNER_VERSION}
ENV DOCKER_VERSION=5:29.8.2-1~ubuntu.22.04~jammy
"""

# cloudenv uses the `ENV KEY value` form and has many *_VERSION entries.
CLOUDENV = "FROM debian:trixie-20260918-slim\n" + "".join(
    f"ENV {name}_VERSION 1.{i}.0\nENV {name}_URL https://example.org/v${{{name}_VERSION}}\n"
    f"ENV {name}_SHA256 {'0' * 64}\n"
    for i, name in enumerate(
        "KUBECTL HELM TERRAFORM TERRAGRUNT PACKER AWS_IAM_AUTH KUBECTX KOMPOSE K9S "
        "FLUX2 KUBESPY EKSCTL AWSSMP CLOUD_NUKE CONFD".split()
    )
)


class ImageTagTests(unittest.TestCase):
    def envs(self, text):
        path = write_dockerfile(text)
        self.addCleanup(os.unlink, path)
        return de.collect_envs(path)

    def test_single_folder_tag_is_main_version_only(self):
        envs = self.envs(DFUPDATE)
        self.assertEqual(de.build_alias(envs, "DFUPDATE_VERSION", "."), "2.2.2")

    def test_folder_prefix_main_not_first(self):
        envs = self.envs(SAW)
        self.assertEqual(de.build_alias(envs, "SAGE_VERSION", "cu12"), "cu12-2.2.0")

    def test_ghrunner_dependency_with_illegal_chars_is_not_in_tag(self):
        envs = self.envs(GHRUNNER)
        self.assertEqual(de.build_alias(envs, "GHRUNNER_VERSION", "."), "2.337.0")
        self.assertEqual(
            de.build_versions(envs, "13.0.3-base-ubuntu24.04")["DOCKER_VERSION"],
            "5:29.8.2-1~ubuntu.22.04~jammy",
        )

    def test_cloudenv_space_form_and_many_versions_stay_short(self):
        envs = self.envs(CLOUDENV)
        self.assertGreaterEqual(
            len([k for k in envs if k.endswith("_VERSION")]), 15
        )
        tag = de.build_alias(envs, "HELM_VERSION", ".")
        self.assertEqual(tag, "1.1.0")
        self.assertLess(len(tag), 128)

    def test_illegal_chars_and_spaces_become_dash(self):
        envs = self.envs("FROM a:1\nENV A_VERSION 5:1.2~rc 1+b\n")
        self.assertEqual(de.build_alias(envs, "A_VERSION", "."), "5-1.2-rc-1-b")

    def test_leading_dot_or_dash_is_made_valid(self):
        self.assertEqual(de.sanitize_tag_part("-x"), "_x")
        self.assertEqual(de.sanitize_tag_part(".x"), "_x")

    def test_multistage_duplicate_key_takes_last_value(self):
        envs = self.envs(
            "FROM a:1 AS build\nENV PYALPM_VERSION 1\n"
            "FROM b:2\nENV PYALPM_VERSION 3\nENV NVCHECKER_VERSION 2.22\n"
        )
        self.assertEqual(de.build_alias(envs, "NVCHECKER_VERSION", "."), "2.22")
        self.assertEqual(
            de.build_versions(envs, "2"),
            {"PYALPM_VERSION": "3", "NVCHECKER_VERSION": "2.22", "BASE": "2"},
        )

    def test_absent_or_unset_main_is_error(self):
        envs = self.envs(SAW)
        with self.assertRaises(ValueError):
            de.build_alias(envs, "NOPE_VERSION", ".")
        with self.assertRaises(ValueError):
            de.build_alias(envs, "", ".")

    def test_over_length_prefixed_tag_rejected(self):
        envs = self.envs("FROM a:1\nENV A_VERSION " + "1" * 125 + "\n")
        self.assertEqual(len(de.build_alias(envs, "A_VERSION", ".")), 125)
        with self.assertRaises(ValueError):
            de.build_alias(envs, "A_VERSION", "cu12")

    def test_bad_folder_rejected(self):
        envs = self.envs(SAW)
        with self.assertRaises(ValueError):
            de.build_alias(envs, "SAGE_VERSION", "a/b")


# Lines of cloudenv's real Dockerfile (space-form ENV), plus the date-version ENV.
CLOUDENV_REAL = """FROM debian:trixie-20260918-slim
ENV CLOUDENV_VERSION 2026-10-04
ENV CLOUDENV_UPGRADE false
ENV KUBECTL_VERSION 1.31.0
ENV KUBECTL_URL https://storage.googleapis.com/kubernetes-release/release/v$KUBECTL_VERSION/bin/linux/amd64
ENV HELM_VERSION 4.3.0
ENV HELM_FILENAME helm-v${HELM_VERSION}-linux-amd64.tar.gz
ENV AWSSMP_VERSION 1.2.536.0
"""


class DateVersionTests(unittest.TestCase):
    def test_next_version(self):
        self.assertEqual(dv.next_version("2026-10-03", "2026-10-04"), "2026-10-04")
        self.assertEqual(dv.next_version("2026-10-04", "2026-10-04"), "2026-10-04-2")
        self.assertEqual(dv.next_version("2026-10-04-2", "2026-10-04"), "2026-10-04-3")
        # a hand-set future date never makes the version go backwards
        self.assertEqual(dv.next_version("2026-10-09", "2026-10-04"), "2026-10-09-2")
        with self.assertRaises(ValueError):
            dv.next_version("1.2.3", "2026-10-04")

    def test_invalid_or_duplicate_env_rejected(self):
        for bad in ("2026-10-04-hotfix", "2026-10-04-0", "1.2.3", "2026-10-4"):
            with self.assertRaises(ValueError, msg=bad):
                dv.read_current(f"ENV X_VERSION {bad}\n", "X_VERSION")
        with self.assertRaises(ValueError):
            dv.read_current("ENV X_VERSION 2026-10-04\nENV X_VERSION 2026-10-05\n", "X_VERSION")
        with self.assertRaises(ValueError):
            dv.read_current("FROM a:1\n", "X_VERSION")
        self.assertEqual(dv.read_current("ENV X_VERSION=2026-10-04-3\n", "X_VERSION"), "2026-10-04-3")

    def test_collision_guard_increments_past_existing_tags(self):
        taken = {"r:cu12-2026-10-11", "r:cu12-2026-10-11-2"}
        dv.tag_exists, orig = (lambda ref: ref in taken), dv.tag_exists
        self.addCleanup(setattr, dv, "tag_exists", orig)
        version = dv.first_free("r", "cu12-", "2026-10-11")
        self.assertEqual(version, "2026-10-11-3")

    def test_read_and_rewrite_keep_form_and_other_lines(self):
        self.assertEqual(dv.read_current(CLOUDENV_REAL, "CLOUDENV_VERSION"), "2026-10-04")
        new = dv.rewrite(CLOUDENV_REAL, "CLOUDENV_VERSION", "2026-10-11")
        self.assertIn("ENV CLOUDENV_VERSION 2026-10-11\n", new)
        self.assertEqual(new.replace("2026-10-11", "2026-10-04"), CLOUDENV_REAL)
        eq = dv.rewrite("ENV X_VERSION=2026-01-01 Y=1\n", "X_VERSION", "2026-02-02")
        self.assertEqual(eq, "ENV X_VERSION=2026-02-02 Y=1\n")

    def test_bump_only_when_dockerfile_changed(self):
        git = lambda *a: subprocess.run(  # noqa: E731
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            git("init", "-q")
            path = os.path.join(tmp, "Dockerfile")
            with open(path, "w") as handle:
                handle.write(CLOUDENV_REAL)
            git("add", "-A")
            git("commit", "-q", "-m", "x")
            cwd = os.getcwd()
            os.chdir(tmp)
            self.addCleanup(os.chdir, cwd)
            argv = ["--path", "Dockerfile", "--main", "CLOUDENV_VERSION"]
            import contextlib
            import io

            def bump(date):
                out = io.StringIO()
                old = sys.argv
                sys.argv = ["date_version.py", *argv, "--run-date", date]
                try:
                    with contextlib.redirect_stdout(out):
                        self.assertEqual(dv.main(), 0)
                finally:
                    sys.argv = old
                return out.getvalue().strip()

            # hand fix / no change: version untouched, file untouched
            self.assertEqual(bump("2026-10-11"), "2026-10-04")
            self.assertEqual(open(path).read(), CLOUDENV_REAL)
            # dfupdate bumped a dependency: new date
            with open(path, "w") as handle:
                handle.write(CLOUDENV_REAL.replace("4.3.0", "4.4.0"))
            self.assertEqual(bump("2026-10-11"), "2026-10-11")
            self.assertIn("ENV CLOUDENV_VERSION 2026-10-11\n", open(path).read())
            # committed on the same date, another change: -2
            git("commit", "-q", "-am", "bot")
            committed = open(path).read()
            with open(path, "w") as handle:
                handle.write(committed.replace("4.4.0", "4.5.0"))
            self.assertEqual(bump("2026-10-11"), "2026-10-11-2")
            self.assertEqual(de_alias(path), "2026-10-11-2")


def de_alias(path):
    return de.build_alias(de.collect_envs(path), "CLOUDENV_VERSION", ".")


class ImageLabelTests(unittest.TestCase):
    L = "io.github.snw35.cicd.context-digest"

    def test_single_manifest(self):
        doc = json.dumps({"config": {"Labels": {self.L: "abc"}}})
        self.assertEqual(il.label_value(doc, self.L), "abc")

    def test_platform_map_agreeing(self):
        one = {"config": {"Labels": {self.L: "abc"}}}
        doc = json.dumps({"linux/amd64": one, "linux/arm64": one})
        self.assertEqual(il.label_value(doc, self.L), "abc")

    def test_platform_map_disagreeing_or_absent_is_empty(self):
        doc = json.dumps(
            {
                "a": {"config": {"Labels": {self.L: "1"}}},
                "b": {"config": {"Labels": {self.L: "2"}}},
            }
        )
        self.assertEqual(il.label_value(doc, self.L), "")
        self.assertEqual(il.label_value(json.dumps({"config": {}}), self.L), "")


class SelectLegsTests(unittest.TestCase):
    def test_ignored_paths(self):
        for path in (
            ".github/workflows/update.yml",
            "README.md",
            "cu12/docs/NOTES.md",
            "LICENSE",
            "cu12/old_ver.json",
            "new_ver.json",
            "cu13/nvchecker.toml",
        ):
            self.assertTrue(sl.is_ignored(path), path)
        for path in ("Dockerfile", "cu12/Dockerfile", "dfupdate.py", "cu13/build.sh"):
            self.assertFalse(sl.is_ignored(path), path)

    def test_selection_rules(self):
        legs = ["cu12", "cu13"]
        self.assertEqual(sl.select_legs(legs, ["cu13/build.sh"]), ["cu13"])
        self.assertEqual(sl.select_legs(legs, ["docker-compose.yml"]), legs)
        self.assertEqual(sl.select_legs(legs, ["README.md", "cu12/x.md"]), [])
        self.assertEqual(sl.select_legs(["neo"], ["neo/x.py"]), ["neo"])
        self.assertEqual(sl.select_legs(["."], ["dfupdate.py"]), ["."])
        self.assertEqual(sl.select_legs(["."], ["README.md"]), [])
        self.assertEqual(
            sl.select_legs([".", "secondary"], ["secondary/a"]), ["secondary"]
        )
        self.assertEqual(sl.select_legs([".", "secondary"], ["a"]), [".", "secondary"])

    def test_partial_recovery_selects_only_the_stale_leg(self):
        legs = ["cu12", "cu13"]
        # A's image is at the tip (nothing changed since); B's label is older and a
        # shared root file changed in between.
        a = sl.plan(legs, "tip", "tip", lambda b, t: True, lambda b, t: [])
        b = sl.plan(legs, "old", "tip", lambda b, t: True, lambda b, t: ["docker-compose.yml"])
        self.assertNotIn("cu12", a)
        self.assertIn("cu13", b)

    def test_bot_only_and_ignored_only_select_nothing(self):
        self.assertEqual(sl.select_legs(["."], ["README.md", "old_ver.json"]), [])
        self.assertEqual(sl.plan(["."], "b", "t", lambda b, t: True, lambda b, t: []), [])

    def test_non_ancestor_base_selects_leg(self):
        self.assertEqual(
            sl.plan(["cu12"], "b", "t", lambda b, t: False, lambda b, t: []), ["cu12"]
        )

    def test_stale_without_label_is_true(self):
        os.environ["WORKDIRS"] = '["."]'
        self.addCleanup(os.environ.pop, "WORKDIRS")
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sl.stale_main(".", "")
        self.assertEqual(out.getvalue().strip(), "true")

    def test_plan_empty_history_selects_all(self):
        def boom(*_):
            raise AssertionError("must not be called")

        self.assertEqual(
            sl.plan(["cu12", "cu13"], None, "t", boom, boom), ["cu12", "cu13"]
        )

    def test_plan_force_push_and_diff_failure_select_all(self):
        legs = ["cu12", "cu13"]
        self.assertEqual(
            sl.plan(legs, "b", "t", lambda b, t: False, lambda b, t: ["cu12/x"]), legs
        )

        def failing(b, t):
            raise subprocess.CalledProcessError(128, "git")

        self.assertEqual(sl.plan(legs, "b", "t", lambda b, t: True, failing), legs)

    def test_plan_normal(self):
        self.assertEqual(
            sl.plan(
                ["cu12", "cu13"], "b", "t", lambda b, t: True, lambda b, t: ["cu12/x"]
            ),
            ["cu12"],
        )


class CollectUpdatesTests(unittest.TestCase):
    def meta(self, workdir, alias, published=False, changed=False, tip="abc"):
        return {
            "workdir": workdir,
            "changed": changed,
            "alias": alias,
            "published": published,
            "tip_sha": tip,
            "digest": "sha256:1",
            "versions": {"X_VERSION": "1", "BASE": "b"},
        }

    def test_name_is_join_of_image_tags_sorted_by_workdir(self):
        metas = [self.meta("cu13", "cu13-2.2.0"), self.meta("cu12", "cu12-2.2.0")]
        result = cu.aggregate(metas, ["cu12", "cu13"], lambda t: False)
        self.assertEqual(result["combined_tag"], "cu12-2.2.0-cu13-2.2.0")

    def test_single_leg_name_is_the_tag(self):
        result = cu.aggregate([self.meta(".", "1")], ["."], lambda t: False)
        self.assertEqual(result["combined_tag"], "1")

    def test_existing_tag_creates_no_release(self):
        # dependency-only or hand-fix publish: release body refresh, no new tag
        result = cu.aggregate(
            [self.meta(".", "1", published=True, changed=True)], ["."], lambda t: False
        )
        self.assertFalse(result["release_needed"])
        self.assertTrue(result["published_any"])
        self.assertFalse(result["blocked"])

    def test_missing_tag_needs_release(self):
        result = cu.aggregate([self.meta(".", "1")], ["."], lambda t: True)
        self.assertTrue(result["release_needed"])

    def test_missing_leg_meta_blocks(self):
        metas = [self.meta("cu12", "cu12-1", published=True)]
        result = cu.aggregate(metas, ["cu12", "cu13"], lambda t: True)
        self.assertEqual(result["blocking"], ["cu13"])
        self.assertFalse(result["release_needed"])
        self.assertTrue(result["blocked"])

    def test_missing_leg_without_publish_or_new_tag_is_not_blocked(self):
        metas = [self.meta("cu12", "cu12-1")]
        result = cu.aggregate(metas, ["cu12", "cu13"], lambda t: False)
        self.assertFalse(result["blocked"])

    def test_body_is_deterministic_and_marks_state(self):
        metas = [self.meta(".", "1", published=True)]
        one = cu.release_body(metas, "1", "deadbeef")
        self.assertEqual(one, cu.release_body(metas, "1", "deadbeef"))
        self.assertIn("<!-- cicd-state-sha: deadbeef -->", one)
        self.assertIn("X_VERSION: `1`", one)
        self.assertIn("sha256:1", one)

    def test_differing_tip_sha_is_error(self):
        metas = [
            self.meta("a", "a-1", tip="x"),
            self.meta("b", "b-1", tip="y"),
        ]
        with self.assertRaises(ValueError):
            cu.aggregate(metas, [], lambda t: False)

    def test_main_writes_outputs_and_fails_without_metas(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            env = {
                "UPDATES_DIR": tmp,
                "GITHUB_OUTPUT": out,
                "RELEASE_BODY_FILE": os.path.join(tmp, "body.md"),
            }
            old = {k: os.environ.get(k) for k in env}
            os.environ.update(env)
            try:
                self.assertEqual(cu.main(), 1)
                with open(os.path.join(tmp, "x-meta.json"), "w") as handle:
                    json.dump(
                        {
                            "workdir": ".",
                            "changed": "true",
                            "published": "true",
                            "alias": "1",
                            "tip_sha": "s",
                        },
                        handle,
                    )
                cu.git_tag_missing = lambda tag, remote="origin": True
                self.assertEqual(cu.main(), 0)
                text = open(out).read()
                self.assertIn("release_needed=true", text)
                self.assertIn("combined_tag=1", text)
            finally:
                for key, value in old.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
