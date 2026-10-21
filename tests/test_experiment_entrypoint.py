from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_experiments.sh"


class ExperimentEntrypointTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), *args], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )

    def test_no_arguments_prints_help_without_running(self):
        result = self.run_script()
        self.assertEqual(0, result.returncode)
        self.assertIn("Usage:", result.stdout)

    def test_paid_provider_requires_explicit_opt_in(self):
        result = self.run_script("--model", "openai:gpt-example", "--dataset", "hospital", "--dry-run")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("--allow-paid-api", result.stdout)

    def test_mock_dry_run_prints_pipeline_command(self):
        result = self.run_script("--model", "mock:echo", "--dataset", "hospital", "--dry-run")
        self.assertEqual(0, result.returncode)
        self.assertIn("src.pipeline", result.stdout)
        self.assertIn("--datasets hospital", result.stdout)

    def test_unknown_dataset_is_rejected(self):
        result = self.run_script("--model", "mock:echo", "--dataset", "unknown", "--dry-run")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unknown dataset", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
