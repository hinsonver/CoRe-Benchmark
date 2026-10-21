from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))


class PortabilityTests(unittest.TestCase):
    def test_data_paths_are_artifact_relative(self):
        from src import data

        self.assertEqual(ROOT, data.ROOT)
        self.assertEqual(ROOT / "data" / "final", data.RAW)

    def test_archived_p2_path_is_artifact_relative(self):
        from src import probe_clean

        self.assertEqual(ROOT / "artifacts" / "raw_outputs" / "p2", probe_clean.OUT)

    def test_release_text_has_no_private_absolute_paths(self):
        forbidden = ("/Users/oki", "/data/YJR")
        findings = []
        # The validator itself contains these literals as search patterns.
        for base in (ROOT / "code", ROOT / "scripts"):
            for path in base.rglob("*"):
                if not path.is_file() or path.suffix in {".pyc"}:
                    continue
                text = path.read_text(errors="ignore")
                for needle in forbidden:
                    if needle in text:
                        findings.append(f"{path.relative_to(ROOT)}: {needle}")
        self.assertFalse(findings, "private paths found: " + ", ".join(findings))

    def test_clients_do_not_automatically_load_dotenv(self):
        text = (ROOT / "code/src/clients.py").read_text()
        self.assertNotIn("load_dotenv(ROOT / \".env\")", text)


if __name__ == "__main__":
    unittest.main()
