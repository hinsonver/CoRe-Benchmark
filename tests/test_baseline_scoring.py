"""Offline baseline replay contracts; fixtures contain no licensed movie records."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


class BaselineScoringTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / "tools/score_baselines.py"
        self.assertTrue(path.is_file(), "offline raw baseline scorer is not implemented")
        spec = importlib.util.spec_from_file_location("score_baselines", path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.ns = self.mod.frozen_functions(ROOT)
        self.dirty = pd.DataFrame({"ProviderNumber": ["bad", "okay"], "other": ["x", "bad"]})
        self.clean = pd.DataFrame({"ProviderNumber": ["Right", "okay"], "other": ["x", "good"]})

    def test_normalization_noop_and_exact_error_definition(self):
        output = pd.DataFrame({"ProviderNumber": [" RIGHT ", " OKAY "], "other": [" x ", "good"]})
        got = self.mod.score_table(self.dirty, self.clean, output, set(), {"ProviderNumber"}, self.ns)
        self.assertEqual(got["all"]["errors"], 2)
        self.assertEqual(got["all"]["predicted"], 2)
        self.assertEqual(got["all"]["repaired"], 2)
        self.assertEqual(got["identity"]["repair_f1"], 1.0)

    def test_development_rows_are_excluded_from_errors_and_predictions(self):
        got = self.mod.score_table(self.dirty, self.clean, self.clean, {0}, {"ProviderNumber"}, self.ns)
        self.assertEqual(got["all"]["errors"], 1)
        self.assertEqual(got["identity"]["errors"], 0)

    def test_output_shape_is_checked(self):
        with self.assertRaisesRegex(ValueError, "shape"):
            self.mod.score_table(self.dirty, self.clean, self.clean.iloc[:1], set(), set(), self.ns)

    def test_bad_fix_positions_fail_instead_of_silently_disappearing(self):
        for fixes in ([[2, "ProviderNumber", "Right"]], [[0, "not-a-column", "Right"]], [[True, "other", "good"]]):
            with self.subTest(fixes=fixes), self.assertRaisesRegex(ValueError, "fix"):
                self.mod.score_fixes(self.dirty, self.clean, fixes, {"ProviderNumber"}, self.ns)

    def test_whole_table_fixes_count_correct_cell_changes(self):
        got = self.mod.score_fixes(self.dirty, self.clean, [[0, "ProviderNumber", "right"], [0, "other", "wrong"]], {"ProviderNumber"}, self.ns)
        self.assertEqual(got["all"]["predicted"], 2)
        self.assertEqual(got["all"]["detected"], 1)

    def test_missing_fix_payload_is_honestly_count_only(self):
        record = {"dataset": "hospital", "mode": "perfect", "seed": 0,
                  "corrections": 1, "detected": 2, "seconds": 1}
        counts = self.mod.score_fixes(self.dirty, self.clean, [[0, "ProviderNumber", "right"]], {"ProviderNumber"}, self.ns)
        record["counts"] = {g: {k: v[k] for k in self.mod.COUNT_KEYS} for g, v in counts.items()}
        record.update(counts)
        got = self.mod.score_e5_record("hospital__perfect__seed0.json", record, self.dirty, self.clean, self.ns)
        self.assertEqual(got["status"], "archived_count_only")
        self.assertFalse(got["raw_verified"])

    def test_altered_e5_metadata_fails(self):
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.mod.score_e5_record("hospital__perfect__seed0.json", {"dataset": "hospital", "mode": "raha", "seed": 0}, self.dirty, self.clean, self.ns)

    def test_archive_discrepancies_are_reported_not_replaced(self):
        differences = []
        self.mod.compare_values({"errors": 1}, {"errors": 2}, "run/all", differences)
        self.assertEqual(differences, [{"location": "run/all/errors", "reconstructed": 1, "archived": 2}])

    def test_runtime_summary_retains_original_numpy_rounding(self):
        self.assertTrue(hasattr(self.mod, "runtime_minutes"), "exact archived runtime arithmetic is missing")
        self.assertEqual(self.mod.runtime_minutes([3, 3, 3]), 0.0)

    def test_development_sample_full_values_checked(self):
        dirty = pd.DataFrame({"x": [str(i) for i in range(20)]})
        dev = dirty.sample(n=4, random_state=42).reset_index(drop=True)
        self.assertEqual(len(self.mod.development_indices(dirty, dev)), 4)
        dev.at[0, "x"] = "altered"
        with self.assertRaisesRegex(ValueError, "development"):
            self.mod.development_indices(dirty, dev)

    def test_aligned_labels_are_excluded_and_only_error_cells_score(self):
        chunks = [{"chunk": 0, "rows": [1], "fixes": [[1, "other", "good"], [1, "ProviderNumber", "wrong"]]}]
        got = self.mod.score_aligned(self.dirty, self.clean, chunks, [[1]], {"ProviderNumber"}, self.ns)
        self.assertEqual(got[0]["counts"]["all"], {"errors": 1, "predicted": 1, "repaired": 1, "detected": 1})
        chunks[0]["rows"] = [0, 1]
        with self.assertRaisesRegex(ValueError, "rows"):
            self.mod.score_aligned(self.dirty, self.clean, chunks, [[1]], {"ProviderNumber"}, self.ns)

    def test_duplicate_chunk_ids_fail(self):
        with self.assertRaisesRegex(ValueError, "chunk"):
            self.mod.score_aligned(self.dirty, self.clean, [{"chunk": 1, "rows": [1], "fixes": []}], [[1]], set(), self.ns)

    def test_labels_validation_and_surrogate_reuse(self):
        self.assertEqual(self.mod.label_source("hospital_surrogatewords", "hospital"), "hospital")
        self.assertEqual(self.mod.label_source("beers_surrogate", "beers"), "beers_orig")
        self.assertEqual(self.mod.label_source("hospital_fresh", "hospital"), "hospital_fresh")
        with self.assertRaisesRegex(ValueError, "labels"):
            self.mod.validate_labels([0, 0], 1000)

    def test_missing_input_fails(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(FileNotFoundError):
            self.mod.read_frame(Path(tmp) / "absent.csv")

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result"
            path.mkdir()
            marker = path / "keep.json"
            marker.write_text("unchanged")
            with self.assertRaises(FileExistsError):
                self.mod.write_report(path, {"status": "new"})
            self.assertEqual(marker.read_text(), "unchanged")

    def test_movie_payload_cannot_leak_into_report(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "payload"):
            self.mod.write_report(Path(tmp) / "new", {"fixes": [[0, "Director", "not allowed"]]})

    def test_evidence_rejects_missing_and_changed_bound_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifests = root / "data/manifests"
            manifests.mkdir(parents=True)
            (manifests / "CORE_SOURCES.json").write_text(json.dumps({"original_files": {"saved.json": "0" * 64}, "private_files": {}}))
            (manifests / "RAYYAN_REPLAY.json").write_text(json.dumps({"files": {}}))
            evidence = self.mod.Evidence(root)
            with self.assertRaises(FileNotFoundError):
                evidence.path("saved.json")
            (root / "saved.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "hash"):
                evidence.path("saved.json")

    def test_optional_history_requires_authorization_record(self):
        with self.assertRaisesRegex(ValueError, "together"):
            self.mod.Evidence(ROOT, historical_root="/not-used")

    def aligned_inventory_fixture(self, root, condition="hospital"):
        self.assertTrue(hasattr(self.mod.Evidence, "aligned_seeded_inventory"),
                        "exact seeded archive inventory guard is missing")
        relative = "artifacts/raw_outputs/aligned/"
        names = [relative + f"baran__{condition}__run{k}.json" for k in range(3)]
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[]")
        manifests = root / "data/manifests"
        manifests.mkdir(parents=True)
        bindings = {name: self.mod.digest(root / name) for name in names}
        (manifests / "CORE_SOURCES.json").write_text(json.dumps({"original_files": bindings, "private_files": {}}))
        (manifests / "RAYYAN_REPLAY.json").write_text(json.dumps({"files": {}}))
        return self.mod.Evidence(root), names

    def test_aligned_seeded_inventory_requires_exact_bound_and_physical_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence, names = self.aligned_inventory_fixture(Path(tmp))
            self.assertEqual(evidence.aligned_seeded_inventory(["hospital"]), {"hospital": names})

    def test_additional_aligned_seed_file_cannot_be_silently_ignored(self):
        for suffix in ("3", "odd"):
            for layer in ("physical", "bindings", "both"):
                with self.subTest(suffix=suffix, layer=layer), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    evidence, _ = self.aligned_inventory_fixture(root)
                    extra = f"artifacts/raw_outputs/aligned/baran__hospital__run{suffix}.json"
                    if layer != "bindings":
                        (root / extra).write_text("[]")
                    if layer != "physical":
                        evidence.bindings[extra] = "0" * 64
                    with self.assertRaisesRegex(ValueError, "seeded.*inventory"):
                        evidence.aligned_seeded_inventory(["hospital"])

    def test_missing_aligned_seed_run_is_rejected_in_bindings_or_files(self):
        for layer in ("bindings", "physical"):
            with self.subTest(layer=layer), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                evidence, names = self.aligned_inventory_fixture(root)
                if layer == "bindings":
                    del evidence.bindings[names[-1]]
                else:
                    (root / names[-1]).unlink()
                with self.assertRaisesRegex(ValueError, "seeded.*inventory"):
                    evidence.aligned_seeded_inventory(["hospital"])

    def test_authorized_movie_inventory_uses_private_physical_root(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as history:
            root, private = Path(tmp), Path(history)
            evidence, names = self.aligned_inventory_fixture(root, "movies")
            evidence.private = private
            evidence.private_bindings = {name: evidence.bindings[name] for name in names}
            for name in names:
                (private / name).parent.mkdir(parents=True, exist_ok=True)
                (private / name).write_text("[]")
            self.assertEqual(evidence.aligned_seeded_inventory(["movies"]), {"movies": names})
            extra = "artifacts/raw_outputs/aligned/baran__movies__run3.json"
            (private / extra).write_text("[]")
            with self.assertRaisesRegex(ValueError, "seeded.*inventory"):
                evidence.aligned_seeded_inventory(["movies"])

    def test_replay_rejects_extra_seed_before_loading_or_scoring_raw_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, _ = self.aligned_inventory_fixture(root)
            (root / "artifacts/raw_outputs/aligned/baran__hospital__run3.json").write_text("[]")
            with patch.object(self.mod, "Evidence", return_value=evidence), \
                    patch.object(self.mod, "frozen_functions", side_effect=AssertionError("scoring started")):
                with self.assertRaisesRegex(ValueError, "seeded.*inventory"):
                    self.mod.replay(root)

    def test_saved_reply_and_parsed_fixes_must_agree(self):
        chunk = {"chunk": 0, "rows": [1], "fixes": [[1, "other", "good"]], "output": '{"corrections": []}'}
        with self.assertRaisesRegex(ValueError, "parsed"):
            self.mod.score_aligned(self.dirty, self.clean, [chunk], [[1]], set(), self.ns)

    def test_csv_shape_rejects_ragged_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ragged.csv"
            path.write_text("a,b\n1\n")
            with self.assertRaisesRegex(ValueError, "shape"):
                self.mod.read_frame(path)

    def test_legacy_unseeded_row_mismatch_is_reported_not_raw_verified(self):
        self.assertTrue(hasattr(self.mod, "aligned_record"), "historical mismatch disposition is missing")
        saved = [{"chunk": 0, "rows": [0], "fixes": [[0, "ProviderNumber", "Right"]]}]
        record, chunks = self.mod.aligned_record("baran__hospital_fresh", self.dirty, self.clean, saved, [[1]], {"ProviderNumber"}, self.ns)
        self.assertFalse(record["raw_verified"])
        self.assertEqual(record["status"], "historical_row_metadata_mismatch")
        self.assertEqual(record["metadata_discrepancy"]["mismatched_chunks"], 1)
        self.assertEqual(chunks[0]["counts"]["all"]["repaired"], 1)

    def test_selected_seeded_row_mismatch_still_fails_closed(self):
        self.assertTrue(hasattr(self.mod, "aligned_record"), "historical mismatch disposition is missing")
        saved = [{"chunk": 0, "rows": [0], "fixes": []}]
        with self.assertRaisesRegex(ValueError, "rows"):
            self.mod.aligned_record("baran__hospital_fresh__run0", self.dirty, self.clean, saved, [[1]], set(), self.ns)


if __name__ == "__main__":
    unittest.main()
