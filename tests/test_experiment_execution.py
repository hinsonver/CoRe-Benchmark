"""Execution preparation contracts; these tests never run a model or baseline."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/experiments.py"


class ExperimentExecutionTests(unittest.TestCase):
    def checkout_fixture(self, directory):
        """Small non-executed source tree; Git command responses are injected."""
        root = Path(directory)
        files = {name: b"# fixture\n" for name in
                 ("main.py", "pipeline.py", "config.py", "executor.py", "skills.md", "error_types.txt", "requirements.txt")}
        for name, content in files.items():
            (root / name).write_bytes(content)
        tree = b"".join(b"100644 blob " + hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest().encode()
                        + b"\t" + name.encode() + b"\0" for name, content in files.items())
        objects = {hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest(): content
                   for content in files.values()}
        def git(command, **kwargs):
            if "--show-toplevel" in command:
                return SimpleNamespace(returncode=0, stdout=str(root).encode() + b"\n", stderr=b"")
            if "rev-parse" in command:
                return SimpleNamespace(returncode=0, stdout=b"ae292b6ff8118c8786cd7c97364e9a8a07f00b62\n", stderr=b"")
            if "ls-tree" in command:
                return SimpleNamespace(returncode=0, stdout=tree, stderr=b"")
            if "cat-file" in command:
                return SimpleNamespace(returncode=0, stdout=objects[command[-1]], stderr=b"")
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        return root, git

    def check_checkout(self, m, root):
        a = self.args(m, "--experiment", "tabclean", "--model", "custom:deepseek/deepseek-v4-pro",
                      "--tabclean-root", str(root), "--preflight")
        return m.preflight(m.make_plan(a, ROOT), a, ROOT)

    def module(self):
        self.assertTrue(TOOL.is_file(), "safe experiment planner is missing")
        spec = importlib.util.spec_from_file_location("experiment_execution_under_test", TOOL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def args(self, module, *extra):
        return module.parser().parse_args([
            "--experiment", "cleaning", "--dataset", "hospital",
            "--model", "local:qwen2.5-7b", *extra,
        ])

    def test_help_does_not_import_experiment_clients(self):
        self.assertTrue(TOOL.is_file(), "safe experiment planner is missing")
        result = subprocess.run([sys.executable, str(TOOL), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--preflight", result.stdout)
        self.assertIn("--execute", result.stdout)

    def test_default_plan_is_read_only_and_has_real_module(self):
        m = self.module()
        clients_before = sys.modules.get("src.clients")
        with patch.object(socket, "socket", side_effect=AssertionError("network")):
            plan = m.make_plan(self.args(m), ROOT)
        self.assertEqual(plan["action"], "plan")
        self.assertEqual(plan["module"], "src.probe_clean")
        self.assertIs(clients_before, sys.modules.get("src.clients"))
        self.assertEqual(plan["table"], "hospital")
        self.assertTrue(plan["output_directory"].startswith(str(ROOT / "build/experiment-runs")))
        self.assertFalse(Path(plan["output_directory"]).exists())

    def test_unsupported_model_and_dataset_are_rejected(self):
        m = self.module()
        for extra in (("--model", "local:new-model"), ("--dataset", "rayyan")):
            with self.assertRaises(ValueError):
                m.make_plan(self.args(m, *extra), ROOT)

    def test_beers_extra_construction_seed_rejected(self):
        m = self.module()
        with self.assertRaisesRegex(ValueError, "construction"):
            m.make_plan(self.args(m, "--dataset", "beers", "--condition", "F",
                                  "--construction-seed", "1"), ROOT)

    def test_original_condition_cannot_gain_extra_construction_seed(self):
        m = self.module()
        with self.assertRaisesRegex(ValueError, "construction"):
            m.make_plan(self.args(m, "--construction-seed", "1"), ROOT)

    def test_hospital_existing_construction_seed_selects_exact_table(self):
        m = self.module()
        p = m.make_plan(self.args(m, "--condition", "W", "--construction-seed", "2"), ROOT)
        self.assertEqual(p["table"], "hospital_surrogatewords_s2")
        self.assertIn("__hospital_surrogatewords_s2__k20__spread.json", p["historical_output"])

    def test_continuation_combinations_follow_actual_archive(self):
        m = self.module()
        p = m.make_plan(self.args(m, "--experiment", "continuation", "--dataset", "flights"), ROOT)
        self.assertEqual(p["module"], "src.probe_rowcont")
        with self.assertRaisesRegex(ValueError, "archived"):
            m.make_plan(self.args(m, "--experiment", "continuation",
                                  "--model", "openai:gpt-6.1-sol"), ROOT)

    def test_conflicts_never_schedule_screening_or_reconstruction(self):
        m = self.module()
        p = m.make_plan(self.args(m, "--experiment", "conflicts"), ROOT)
        self.assertEqual(p["module"], "src.near_entities")
        self.assertEqual(p["entrypoint"], "run")
        self.assertFalse(any(x in json.dumps(p["invocation"]) for x in ("screen", "candidates", "build(")))

    def test_output_must_be_new_non_symlink_under_dedicated_build_root(self):
        m = self.module()
        for name in (str(ROOT / "artifacts/raw_outputs/p2"), str(ROOT / "build"), "/tmp/core-run"):
            with self.assertRaisesRegex(ValueError, "output"):
                m.make_plan(self.args(m, "--output-dir", name), ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as tmp:
            with self.assertRaisesRegex(ValueError, "output"):
                m.make_plan(self.args(m, "--output-dir", tmp), ROOT)

    def test_preflight_does_not_contact_services_or_read_response_cache(self):
        m = self.module()
        p = m.make_plan(self.args(m, "--preflight"), ROOT)
        with patch.object(socket, "socket", side_effect=AssertionError("network")):
            result = m.preflight(p, self.args(m, "--preflight"), ROOT)
        self.assertEqual(result["service_status"], "not_contacted")
        self.assertFalse(result["network_used"])
        self.assertFalse(result["response_cache_read"])

    def test_missing_dependency_blocks_before_output_or_subprocess(self):
        m = self.module()
        a = self.args(m, "--execute", "--allow-network")
        p = m.make_plan(a, ROOT)
        with patch.object(m.importlib.util, "find_spec", return_value=None), \
             patch.object(m.subprocess, "run", side_effect=AssertionError("must not execute")):
            result = m.execute(p, a, ROOT)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("dependency" in b for b in result["blockers"]))
        self.assertFalse(Path(p["output_directory"]).exists())

    def test_execute_requires_explicit_network_acknowledgement(self):
        m = self.module()
        a = self.args(m, "--execute")
        p = m.make_plan(a, ROOT)
        with patch.object(m.subprocess, "run", side_effect=AssertionError("must not execute")):
            result = m.execute(p, a, ROOT)
        self.assertIn("--allow-network", " ".join(result["blockers"]))
        self.assertFalse(Path(p["output_directory"]).exists())

    def test_hosted_legacy_endpoint_not_declared_available_from_env(self):
        m = self.module()
        a = self.args(m, "--model", "custom:deepseek/deepseek-v4-pro", "--preflight")
        with patch.dict(os.environ, {"CUSTOM_BASE_URL": "https://invalid.example", "CUSTOM_API_KEY": "not-a-key"}):
            result = m.preflight(m.make_plan(a, ROOT), a, ROOT)
        self.assertTrue(any("historical hosted" in b for b in result["blockers"]))
        self.assertNotIn("not-a-key", json.dumps(result))
        self.assertEqual(result["service_status"], "not_contacted")

    def test_movies_requires_explicit_authorized_history(self):
        m = self.module()
        a = self.args(m, "--dataset", "movies", "--preflight")
        result = m.preflight(m.make_plan(a, ROOT), a, ROOT)
        self.assertTrue(any("authorization" in b for b in result["blockers"]))
        self.assertNotIn("Movies fallback", json.dumps(result))

    def test_aligned_uses_frozen_labels_and_fixed_algorithm_seed(self):
        m = self.module()
        a = self.args(m, "--experiment", "aligned-baran", "--condition", "F", "--algorithm-seed", "2")
        p = m.make_plan(a, ROOT)
        self.assertEqual(p["module"], "src.aligned")
        self.assertEqual(p["entrypoint"], "baran_chunks")
        self.assertIn("labels_hospital.json", p["copy_inputs"][0][0])
        self.assertEqual(p["algorithm_seed"], 2)

    def test_tabclean_reports_missing_upstream_without_reading_dotenv(self):
        m = self.module()
        a = self.args(m, "--experiment", "tabclean", "--model", "custom:deepseek/deepseek-v4-pro", "--preflight")
        result = m.preflight(m.make_plan(a, ROOT), a, ROOT)
        self.assertTrue(any("TabClean" in b for b in result["blockers"]))
        self.assertFalse(result["response_cache_read"])

    def test_auxiliary_olmo_is_continuation_only(self):
        m = self.module()
        with self.assertRaisesRegex(ValueError, "continuation"):
            m.make_plan(self.args(m, "--model", "local:olmo2-7b"), ROOT)

    def test_base_olmo_historical_filename_exception_is_supported(self):
        m = self.module()
        p = m.make_plan(self.args(m, "--experiment", "continuation",
                                  "--model", "localbase:allenai/OLMo-2-1124-7B"), ROOT)
        self.assertIn("localbase__olmo2-7b__hospital__clean__anon.json", p["historical_output"])

    def test_symlink_output_parent_is_rejected(self):
        m = self.module()
        base = ROOT / "build/experiment-runs"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            link = Path(temp) / "link"
            link.symlink_to(Path(temp), target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                m.safe_output(link / "new", ROOT)

    def test_configured_execution_adapter_is_isolated_without_running_it(self):
        m = self.module()
        base = ROOT / "build/experiment-runs"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            output = Path(temp) / "fresh"
            a = self.args(m, "--execute", "--allow-network", "--output-dir", str(output))
            p = m.make_plan(a, ROOT)
            captured = {}
            def fake_run(command, **kwargs):
                captured.update(command=command, **kwargs)
                self.assertTrue(Path(kwargs["env"]["CORE_CACHE_FILE"]).parent.is_dir(),
                                "hosted client writes usage before creating its cache directory")
                compile(command[3], "<execution-adapter>", "exec")
                return SimpleNamespace(returncode=0)
            with patch.dict(os.environ, {"LOCAL_BASE_URL": "http://127.0.0.1:1/v1",
                                         "CORE_CACHE_FILE": "/must-not-read-cache"}), \
                 patch.object(m.subprocess, "run", side_effect=fake_run):
                result = m.execute(p, a, ROOT)
            self.assertEqual(result["status"], "finished")
            self.assertEqual(captured["cwd"], output)
            self.assertEqual(captured["env"]["CORE_CACHE_FILE"], str(output / "cache/responses.jsonl"))
            self.assertEqual(captured["env"]["CORE_P2_DIR"], str(output / "cleaning"))
            self.assertEqual(captured["env"].get("PYTHONPYCACHEPREFIX"), str(output / "python-cache"))
            self.assertNotIn("src.pipeline", " ".join(captured["command"]))
            self.assertTrue((output / "execution.json").is_file())
            with self.assertRaisesRegex(ValueError, "new directory"):
                m.execute(p, a, ROOT)

    def test_tabclean_never_executes_the_upstream_dotenv_loading_config(self):
        m = self.module()
        self.assertNotIn('importlib.import_module("config")', m.WORKER)
        self.assertIn('sys.modules["config"]=config', m.WORKER)
        self.assertIn('config.MAX_ITERATIONS=10', m.WORKER)

    def test_rayyan_retrieval_keeps_the_bound_sample_without_sampling_or_querying(self):
        m = self.module()
        a = m.parser().parse_args(["--experiment", "rayyan-retrieval", "--dataset", "rayyan", "--preflight"])
        with patch.object(socket, "socket", side_effect=AssertionError("network")):
            p = m.make_plan(a, ROOT)
            result = m.preflight(p, a, ROOT)
        self.assertEqual(p["module"], "src.rayyan_audit")
        self.assertEqual(p["entrypoint"], "pubmed/judge on frozen sample")
        self.assertIn("results/derived/rayyan_audit.json", p["required_inputs"])
        self.assertEqual(p["model"], None)
        self.assertEqual(result["service_status"], "not_contacted")
        self.assertFalse(result["network_used"])

    def test_tabclean_wrong_commit_is_rejected_even_with_all_support_files(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root, git = self.checkout_fixture(temp)
            def wrong_head(command, **kwargs):
                if "rev-parse" in command and "--show-toplevel" not in command:
                    return SimpleNamespace(returncode=0, stdout=b"0" * 40 + b"\n", stderr=b"")
                return git(command, **kwargs)
            with patch.object(m.subprocess, "run", side_effect=wrong_head):
                result = self.check_checkout(m, root)
            self.assertTrue(any("TabClean" in b and "commit" in b for b in result["blockers"]))

    def test_tabclean_dirty_tracked_tree_is_rejected(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root, git = self.checkout_fixture(temp)
            (root / "pipeline.py").write_text("# dirty tracked source\n")
            with patch.object(m.subprocess, "run", side_effect=git):
                result = self.check_checkout(m, root)
            self.assertTrue(any("TabClean" in b and "dirty" in b for b in result["blockers"]))

    def test_tabclean_no_git_checkout_is_rejected(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root, git = self.checkout_fixture(temp)
            with patch.object(m.subprocess, "run", return_value=SimpleNamespace(returncode=128, stdout=b"", stderr=b"not a repository")):
                result = self.check_checkout(m, root)
            self.assertTrue(any("TabClean" in b and "Git" in b for b in result["blockers"]))

    def test_tabclean_missing_support_file_is_rejected(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root, git = self.checkout_fixture(temp)
            (root / "skills.md").unlink()
            with patch.object(m.subprocess, "run", side_effect=git):
                result = self.check_checkout(m, root)
            self.assertTrue(any("TabClean" in b and "missing" in b for b in result["blockers"]))

    def test_tabclean_untracked_importable_source_is_rejected_even_if_ignored(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root, git = self.checkout_fixture(temp)
            def injected(command, **kwargs):
                if "ls-files" in command:
                    return SimpleNamespace(returncode=0, stdout=b"injected.py\0", stderr=b"")
                return git(command, **kwargs)
            with patch.object(m.subprocess, "run", side_effect=injected):
                result = self.check_checkout(m, root)
            self.assertTrue(any("TabClean" in b and "untracked" in b for b in result["blockers"]))

    def test_tabclean_clean_pinned_tree_passes_source_gate_without_importing_it(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root, git = self.checkout_fixture(temp)
            with patch.object(m.subprocess, "run", side_effect=git):
                result = self.check_checkout(m, root)
            self.assertTrue(result.get("tabclean_source_verified"))
            self.assertFalse(any("TabClean" in b for b in result["blockers"]))

    def test_tabclean_source_bytes_cannot_hide_behind_assume_unchanged(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root, git = self.checkout_fixture(temp)
            (root / "executor.py").write_text("# different source\n")
            with patch.object(m.subprocess, "run", side_effect=git):
                result = self.check_checkout(m, root)
            self.assertTrue(any("TabClean" in b and "blob" in b for b in result["blockers"]))

    def real_filter_checkout(self, directory):
        """Real disposable repository; its only filter action creates a marker."""
        base = Path(directory).resolve()
        root = base / "repo"
        root.mkdir()
        self.checkout_fixture(root)
        (root / "other.txt").write_text("tracked non-source asset\n")
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        def git(*args):
            return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                                   "-C", str(root), *args], check=True, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        git("init", "--quiet")
        git("add", "--all")
        git("-c", "user.name=Disposable Test", "-c", "user.email=test@invalid.example",
            "commit", "--quiet", "-m", "Disposable filter regression fixture")
        head = git("rev-parse", "HEAD").decode().strip()
        marker = base / "FILTER-MUST-NOT-EXECUTE"
        attributes = base / "attributes"
        attributes.write_text("* filter=marker\n")
        source = "import pathlib,sys;pathlib.Path(" + repr(str(marker)) + ").write_text('filter executed');sys.stdout.buffer.write(sys.stdin.buffer.read())"
        git("config", "core.attributesFile", str(attributes))
        git("config", "filter.marker.clean", shlex.quote(sys.executable) + " -c " + shlex.quote(source))
        # Invalidate the index stat cache without changing tracked bytes, so the
        # previous git-diff implementation invokes clean even for a clean tree.
        path = root / "main.py"
        stamp = path.stat()
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
        return root, head, marker

    def test_real_git_clean_filter_never_executes_for_clean_checkout(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root, head, marker = self.real_filter_checkout(temp)
            self.assertFalse(marker.exists())
            with patch.object(m, "TABCLEAN_COMMIT", head):
                result = self.check_checkout(m, root)
            self.assertFalse(marker.exists(), "preflight executed repository-local clean filter")
            self.assertTrue(result["tabclean_source_verified"])

    def test_real_git_clean_filter_never_executes_for_dirty_non_source_asset(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as temp:
            root, head, marker = self.real_filter_checkout(temp)
            (root / "other.txt").write_text("changed non-source asset\n")
            self.assertFalse(marker.exists())
            with patch.object(m, "TABCLEAN_COMMIT", head):
                result = self.check_checkout(m, root)
            self.assertFalse(marker.exists(), "preflight executed repository-local clean filter")
            self.assertFalse(result["tabclean_source_verified"])
            self.assertTrue(any("blob" in b for b in result["blockers"]))


if __name__ == "__main__":
    unittest.main()
