from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md",
    "LICENSE",
    "LICENSES.md",
    "environment/requirements.txt",
    "code/src",
    "data/final",
    "data/manifests",
    "artifacts/raw_outputs",
    "results/derived",
    "paper/claim-map.md",
    "docs/reproduction.md",
    "docs/datasets.md",
    "docs/models.md",
    "docs/limitations.md",
    "scripts/verify.sh",
    "scripts/reproduce.sh",
    "scripts/run_experiments.sh",
]


class ReleaseLayoutTests(unittest.TestCase):
    def test_required_release_paths_exist(self):
        missing = [path for path in REQUIRED if not (ROOT / path).exists()]
        self.assertFalse(missing, f"missing release paths: {missing}")


if __name__ == "__main__":
    unittest.main()
