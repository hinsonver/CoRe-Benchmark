import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OutputInventoryTests(unittest.TestCase):
    def test_every_inventory_file_exists(self):
        inventory_path = ROOT / "results/derived/output-inventory.json"
        self.assertTrue(inventory_path.is_file(), str(inventory_path))
        entries = json.loads(inventory_path.read_text())
        missing = [
            entry["relative_path"]
            for entry in entries
            if not (ROOT / entry["relative_path"]).is_file()
        ]
        self.assertFalse(missing, f"missing archived outputs: {missing}")

    def test_inventory_has_all_paper_product_families(self):
        inventory_path = ROOT / "results/derived/output-inventory.json"
        self.assertTrue(inventory_path.is_file(), str(inventory_path))
        entries = json.loads(inventory_path.read_text())
        kinds = {entry["kind"] for entry in entries}
        expected = {"p1", "p2", "near", "aligned", "e4", "e5", "summary", "table", "figure"}
        self.assertEqual(expected, kinds)

    def test_inventory_covers_all_archived_and_reference_products(self):
        entries = json.loads((ROOT / "results/derived/output-inventory.json").read_text())
        recorded = {entry["relative_path"] for entry in entries}
        actual = set()
        for base in (ROOT / "artifacts/raw_outputs", ROOT / "results"):
            for path in base.rglob("*"):
                if path.is_file() and path.name != "output-inventory.json":
                    actual.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(actual, recorded)


if __name__ == "__main__":
    unittest.main()
