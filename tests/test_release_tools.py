import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ReleaseToolTests(unittest.TestCase):
    def test_retained_validation_exception_is_exact(self):
        from tools.check_release import validate_retained_exception

        issues = validate_retained_exception(ROOT / "results/derived/validate_tables.json")
        self.assertEqual([], issues)

    def test_forbidden_file_is_reported(self):
        from tools.check_release import find_forbidden_files

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("SECRET=value")
            self.assertEqual([".env"], find_forbidden_files(root))

    def test_private_path_is_reported_without_file_contents(self):
        from tools.check_release import find_private_paths

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sample.txt").write_text("source=/data/YJR/private")
            self.assertEqual(["sample.txt: /data/YJR"], find_private_paths(root))

    def test_manifest_lines_are_sorted_and_exclude_manifest(self):
        from tools.generate_manifest import manifest_lines

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "z.txt").write_text("z")
            (root / "a.txt").write_text("a")
            (root / "MANIFEST.sha256").write_text("old")
            lines = manifest_lines(root)
            self.assertEqual(["a.txt", "z.txt"], [line.split("  ", 1)[1] for line in lines])


if __name__ == "__main__":
    unittest.main()
