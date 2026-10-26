import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReproductionTests(unittest.TestCase):
    def test_reproduce_builds_paper_products(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                **os.environ,
                "PYTHON": os.environ.get("PYTHON", sys.executable),
                "CORE_MPLCONFIG_DIR": str(ROOT / "build/test-mplconfig"),
            }
            subprocess.run(
                [str(ROOT / "scripts/reproduce.sh"), "--output", str(Path(tmp) / "products")],
                cwd=ROOT,
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            out = Path(tmp) / "products"
            for relative in (
                "derived/seed_summary.json",
                "derived/scale_summary.json",
                "tables/decomposition.tex",
                "tables/p1.tex",
                "figures/fig1_decomposition.csv",
                "figures/fig6_scale.pdf",
            ):
                self.assertTrue((out / relative).is_file(), relative)

            expected = json.loads((ROOT / "results/derived/seed_summary.json").read_text())
            observed = json.loads((out / "derived/seed_summary.json").read_text())
            self.assertEqual(expected, observed)

            for reference_dir, generated_dir, pattern in (
                (ROOT / "results/tables", out / "tables", "*.tex"),
                (ROOT / "results/figures", out / "figures", "*.csv"),
            ):
                references = sorted(reference_dir.glob(pattern))
                self.assertTrue(references)
                for reference in references:
                    generated = generated_dir / reference.name
                    self.assertTrue(generated.is_file(), reference.name)
                    self.assertEqual(reference.read_bytes(), generated.read_bytes(), reference.name)


if __name__ == "__main__":
    unittest.main()
