import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrozenDataTests(unittest.TestCase):
    def test_frozen_table_manifest_matches(self):
        manifest_path = ROOT / "data/manifests/MANIFEST_1002.json"
        self.assertTrue(manifest_path.is_file(), manifest_path)
        manifest = json.loads(manifest_path.read_text())
        for table, files in manifest["tables"].items():
            for name, expected in files.items():
                path = ROOT / "data/final" / table / name
                if table.startswith("movies"):
                    self.assertFalse(path.exists(), "Movie records must remain omitted")
                    binding = json.loads((ROOT / "data/manifests/CORE_SOURCES.json").read_text())
                    self.assertIn(path.relative_to(ROOT).as_posix(), binding["omitted_files"])
                    continue
                self.assertTrue(path.is_file(), str(path))
                observed = hashlib.md5(path.read_bytes()).hexdigest()
                self.assertEqual(expected, observed, str(path))


if __name__ == "__main__":
    unittest.main()
