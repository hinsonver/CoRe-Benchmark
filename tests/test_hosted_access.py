"""Reviewer-owned credentials and model identity checks; no real API calls."""
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def planner():
    spec = importlib.util.spec_from_file_location("hosted_planner", ROOT / "tools/experiments.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostedAccessTests(unittest.TestCase):
    MODEL = "custom:deepseek/deepseek-v4-pro"
    ENV = {"CUSTOM_BASE_URL": "https://reviewer.example/v1", "CUSTOM_API_KEY": "fixture-reviewer-credential"}

    def args(self, m, *extra):
        return m.parser().parse_args(["--experiment", "cleaning", "--dataset", "hospital",
                                      "--model", self.MODEL, *extra])

    def test_complete_reviewer_configuration_is_not_permanently_blocked(self):
        m = planner()
        a = self.args(m, "--preflight")
        with patch.dict(os.environ, self.ENV, clear=True), \
             patch.object(m.importlib.util, "find_spec", return_value=object()), \
             patch.object(socket, "socket", side_effect=AssertionError("network")):
            result = m.preflight(m.make_plan(a), a)
        self.assertEqual(result["status"], "ready_to_attempt")
        self.assertEqual(result["configuration_check"]["status"], "configured")
        self.assertEqual(result["model_version_check"]["confirmation"], "not_confirmed")
        self.assertFalse(result["historical_versions_reverified"])
        self.assertEqual(result["service_status"], "not_contacted")
        self.assertNotIn(self.ENV["CUSTOM_API_KEY"], json.dumps(result))
        self.assertNotIn("reviewer.example", json.dumps(result))

    def test_missing_key_is_configuration_failure_not_model_unavailability(self):
        m = planner()
        a = self.args(m, "--preflight")
        with patch.dict(os.environ, {"CUSTOM_BASE_URL": self.ENV["CUSTOM_BASE_URL"]}, clear=True):
            result = m.preflight(m.make_plan(a), a)
        self.assertEqual(result["configuration_check"]["status"], "incomplete")
        self.assertIn("CUSTOM_API_KEY", " ".join(result["blockers"]))
        self.assertNotIn("unavailable", " ".join(result["blockers"]))

    def test_openai_fallback_key_matches_retained_client(self):
        m = planner()
        a = self.args(m, "--model", "openai:gpt-6.1-sol", "--preflight")
        with patch.dict(os.environ, {"GPT_API_KEY": "fixture-fallback-credential"}, clear=True):
            result = m.preflight(m.make_plan(a), a)
        self.assertEqual(result["configuration_check"]["status"], "configured")
        self.assertNotIn("missing environment variable: OPENAI_API_KEY", result["blockers"])

    def test_missing_openai_key_names_the_primary_environment_variable(self):
        from tools import model_access
        result = model_access.configuration("openai:gpt-6.1-sol", {})
        self.assertEqual(result["required_environment"], ["OPENAI_API_KEY"])

    def test_local_endpoint_rejects_unsupported_scheme(self):
        from tools import model_access
        result = model_access.configuration("local:qwen2.5-7b", {"LOCAL_BASE_URL": "file:///tmp/model"})
        self.assertEqual(result["status"], "invalid")

    def test_invalid_extra_body_never_echoes_its_value(self):
        from tools import model_access
        for value in ("credential-private-text", "[]"):
            with self.subTest(value=value):
                result = model_access.configuration(self.MODEL, {**self.ENV, "CUSTOM_EXTRA_BODY": value})
                self.assertEqual(result["status"], "invalid")
                self.assertNotIn(value, json.dumps(result))

    def test_custom_request_body_cannot_override_model_or_authorization(self):
        from tools import model_access
        for extra in ({"model": "another-model"}, {"headers": {"Authorization": "other-credential"}}):
            with self.subTest(extra=extra):
                result = model_access.configuration(self.MODEL, {**self.ENV, "CUSTOM_EXTRA_BODY": json.dumps(extra)})
                self.assertEqual(result["status"], "invalid")

    def test_placeholder_key_is_not_ready_for_remote_lookup(self):
        from tools import model_access
        for key in ("EMPTY", "YOUR_API_KEY", " "):
            with self.subTest(key=key):
                config = model_access.configuration(self.MODEL, {**self.ENV, "CUSTOM_API_KEY": key})
                self.assertNotEqual(config["status"], "configured")

    def test_custom_extra_body_must_preserve_archived_inference_settings(self):
        from tools import model_access
        for model, expected in ((self.MODEL, {"thinking": {"type": "disabled"}}),
                                ("custom:qwen/qwen3.8-max", {"enable_thinking": False}),
                                ("custom:z-ai/glm-5.3", {"reasoning_effort": "low"})):
            with self.subTest(model=model):
                config = model_access.configuration(model, {**self.ENV, "CUSTOM_EXTRA_BODY": json.dumps(expected)})
                self.assertEqual(config["status"], "configured")
                for changed in ({}, {"reasoning_effort": "high"}, {"thinking": {"type": "enabled"}}):
                    config = model_access.configuration(model, {**self.ENV, "CUSTOM_EXTRA_BODY": json.dumps(changed)})
                    self.assertEqual(config["status"], "invalid")

    def test_execution_environment_does_not_forward_other_account_secrets(self):
        from tools import model_access
        env = {**self.ENV, "PATH": "/usr/bin:/bin", "HOME": "/fixture/home", "LANG": "en_US.UTF-8",
               "MPLCONFIGDIR": "/fixture/mpl", "AWS_ACCESS_KEY_ID": "fixture-access-id",
               "AWS_SECRET_ACCESS_KEY": "fixture-aws-secret", "DATABASE_URL": "fixture-database-secret",
               "GITHUB_TOKEN": "fixture-github-token", "OPENAI_API_KEY": "fixture-other-provider",
               "PYTHONSTARTUP": "/fixture/injection", "CORE_CACHE_FILE": "/fixture/old-cache"}
        result = model_access.execution_environment(self.MODEL, env)
        self.assertEqual(result, {name: env[name] for name in
                                 ("CUSTOM_BASE_URL", "CUSTOM_API_KEY", "PATH", "HOME", "LANG", "MPLCONFIGDIR")})

    def test_malformed_or_credential_bearing_endpoint_is_rejected_without_echo(self):
        m = planner()
        for endpoint in ("not-a-url", "https://user:password@reviewer.example/v1",
                         "https://reviewer.example/v1?key=secret", "https://reviewer.example/v1#secret",
                         "http://reviewer.example/v1"):
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {**self.ENV, "CUSTOM_BASE_URL": endpoint}, clear=True):
                a = self.args(m, "--preflight")
                result = m.preflight(m.make_plan(a), a)
                self.assertEqual(result["configuration_check"]["status"], "invalid")
                self.assertNotIn(endpoint, json.dumps(result))

    def test_model_confirmation_cannot_select_a_substitute(self):
        m = planner()
        with self.assertRaisesRegex(ValueError, "confirmation"):
            m.make_plan(self.args(m, "--confirm-model-version", "custom:another-model"))

    def test_paid_flags_do_not_replace_model_confirmation(self):
        m = planner()
        a = self.args(m, "--execute", "--allow-network", "--allow-paid-api")
        with patch.dict(os.environ, self.ENV, clear=True), \
             patch.object(m.importlib.util, "find_spec", return_value=object()), \
             patch.object(m.subprocess, "run", side_effect=AssertionError("must not execute")):
            plan = m.make_plan(a)
            result = m.execute(plan, a)
        self.assertIn("--confirm-model-version", " ".join(result["blockers"]))
        self.assertFalse(Path(plan["output_directory"]).exists())

    def test_confirmed_hosted_run_reaches_adapter_with_own_key_and_new_output(self):
        m = planner()
        base = ROOT / "build/experiment-runs"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            output = Path(tmp) / "new-run"
            a = self.args(m, "--execute", "--allow-network", "--allow-paid-api",
                          "--confirm-model-version", self.MODEL, "--output-dir", str(output))
            observed = {}
            def child(command, **kw):
                observed.update(kw)
                return SimpleNamespace(returncode=0)
            with patch.dict(os.environ, {**self.ENV, "UNRELATED_API_KEY": "unrelated-fixture"}, clear=True), \
                 patch.object(m.importlib.util, "find_spec", return_value=object()), \
                 patch.object(m.subprocess, "run", side_effect=child):
                result = m.execute(m.make_plan(a), a)
            self.assertEqual(result["status"], "finished")
            self.assertEqual(observed["env"]["CUSTOM_API_KEY"], self.ENV["CUSTOM_API_KEY"])
            self.assertNotIn("UNRELATED_API_KEY", observed["env"])
            metadata = (output / "execution.json").read_text()
            self.assertNotIn(self.ENV["CUSTOM_API_KEY"], metadata)
            self.assertNotIn("reviewer.example", metadata)
            self.assertIn("operator_confirmed_identifier", metadata)

    def test_metadata_lookup_requires_explicit_network_permission(self):
        m = planner()
        a = self.args(m, "--check-model")
        with patch.dict(os.environ, self.ENV, clear=True), \
             patch.object(socket, "socket", side_effect=AssertionError("network")):
            result = m.check_model(m.make_plan(a), a)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["network_used"])

    def lookup(self, response=None, error=None):
        from tools import model_access
        with patch.dict(os.environ, self.ENV, clear=True), \
             patch.object(model_access.urllib.request.OpenerDirector, "open",
                          side_effect=error, return_value=io.BytesIO(json.dumps(response).encode())) as opened:
            result = model_access.lookup_model(self.MODEL, allow_network=True)
        return result, opened

    def test_metadata_lookup_uses_encoded_exact_identifier_without_prompt_or_cache(self):
        result, opened = self.lookup({"id": "deepseek/deepseek-v4-pro", "object": "model"})
        self.assertEqual(result["status"], "model_identifier_advertised")
        self.assertFalse(result["historical_versions_reverified"])
        self.assertTrue(result["network_used"])
        request = opened.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/models/deepseek%2Fdeepseek-v4-pro"))
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertNotIn(self.ENV["CUSTOM_API_KEY"], json.dumps(result))

    def test_wrong_advertised_identifier_is_not_a_version_match(self):
        result, _ = self.lookup({"id": "another-model"})
        self.assertEqual(result["status"], "identifier_mismatch")

    def test_http_errors_are_classified_without_exposing_remote_error_body(self):
        for code, expected in ((401, "authentication_rejected"), (403, "authorization_rejected"),
                               (404, "not_found_or_lookup_unsupported"), (405, "not_found_or_lookup_unsupported"),
                               (429, "rate_limited"), (503, "service_error")):
            with self.subTest(code=code):
                error = HTTPError(self.ENV["CUSTOM_BASE_URL"], code, self.ENV["CUSTOM_API_KEY"], {},
                                  io.BytesIO(self.ENV["CUSTOM_API_KEY"].encode()))
                result, _ = self.lookup(error=error)
                self.assertEqual(result["status"], expected)
                self.assertNotIn(self.ENV["CUSTOM_API_KEY"], json.dumps(result))

    def test_network_failure_does_not_assert_model_retirement(self):
        result, _ = self.lookup(error=URLError(self.ENV["CUSTOM_API_KEY"]))
        self.assertEqual(result["status"], "unreachable")
        self.assertFalse(result["historical_versions_reverified"])
        self.assertNotIn(self.ENV["CUSTOM_API_KEY"], json.dumps(result))

    def test_invalid_response_is_not_identity_evidence(self):
        result, _ = self.lookup(["unexpected"])
        self.assertEqual(result["status"], "invalid_response")

    def test_redirect_handler_does_not_forward_authorization(self):
        from tools import model_access
        request = model_access.urllib.request.Request("https://reviewer.example/v1/models/test",
                                                      headers={"Authorization": "Bearer fixture"})
        self.assertIsNone(model_access._NoRedirect().redirect_request(request, None, 302, "moved", {},
                                                                    "https://elsewhere.example/"))

    def test_metadata_lookup_does_not_import_clients_or_use_environment_proxies(self):
        from tools import model_access
        before = sys.modules.get("src.clients")
        captured = {}
        real_build = model_access.urllib.request.build_opener
        def build(*handlers):
            captured["handlers"] = handlers
            return real_build(*handlers)
        with patch.object(model_access.urllib.request, "build_opener", side_effect=build):
            self.lookup({"id": "deepseek/deepseek-v4-pro"})
        self.assertIs(sys.modules.get("src.clients"), before)
        self.assertEqual(captured["handlers"][0].proxies, {})

    def test_model_free_route_cannot_trigger_a_catalogue_request(self):
        m = planner()
        a = m.parser().parse_args(["--experiment", "rayyan-retrieval", "--dataset", "rayyan", "--check-model"])
        with self.assertRaisesRegex(ValueError, "model"):
            m.make_plan(a)

    def test_version_confirmation_is_not_proof_of_historical_weights(self):
        m = planner()
        a = self.args(m, "--preflight", "--confirm-model-version", self.MODEL)
        with patch.dict(os.environ, self.ENV, clear=True):
            result = m.preflight(m.make_plan(a), a)
        self.assertEqual(result["model_version_check"]["confirmation"], "operator_confirmed_identifier")
        self.assertFalse(result["historical_versions_reverified"])


if __name__ == "__main__":
    unittest.main()
