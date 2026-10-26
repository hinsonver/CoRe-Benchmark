"""Saved continuation replies must be judged offline, never summary-projected."""
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCORER = ROOT / "tools/score_continuations.py"


def scorer():
    if not SCORER.exists():
        return None
    spec = importlib.util.spec_from_file_location("continuation_scoring", SCORER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContinuationScoringTests(unittest.TestCase):
    def setUp(self):
        self.sc = scorer()
        self.assertIsNotNone(self.sc, "offline continuation scorer is not implemented")

    @staticmethod
    def frames():
        clean = pd.DataFrame({"index": [str(i) for i in range(8)],
                              "value": [f"unique-{i}" for i in range(8)]})
        dirty = clean.copy()
        dirty.loc[3, "value"] = "mistake"
        return dirty, clean

    @staticmethod
    def settings(**changes):
        value = dict(model="test:offline", dataset="beers", source="dirty", named=False,
                     n=1, k=2, seed=0, error_rows=False)
        value.update(changes)
        return value

    def archive(self, output, **settings):
        dirty, clean = self.frames()
        config = self.settings(**settings)
        row = self.sc.sample_rows(dirty, clean, config)[0]
        return {"summary": config, "trials": [{"row": row, "output": output,
                                               "parsed": True}]}, dirty, clean, row

    def test_sampling_uses_hundred_prefix_and_error_filter(self):
        clean = pd.DataFrame({"v": [str(i) for i in range(150)]})
        dirty = clean.copy()
        dirty.loc[[10, 20, 30], "v"] = "error"
        config = self.settings(n=5, k=10)
        expected = random.Random(0).sample(list(range(10, 150)), 100)[:5]
        self.assertEqual(self.sc.sample_rows(dirty, clean, config), expected)
        config.update(n=2, error_rows=True)
        self.assertEqual(self.sc.sample_rows(dirty, clean, config),
                         random.Random(0).sample([10, 20, 30], 3)[:2])

    def test_counter_excluded_but_exact_row_checks_counter(self):
        archive, dirty, clean, row = self.archive("placeholder")
        archive["trials"][0]["output"] = f"wrong,{dirty.iloc[row]['value']}"
        result = self.sc.rescore_archive(archive, dirty, clean)
        summary = result["summary"]
        self.assertEqual(summary["skipped_counter_cols"], ["index"])
        self.assertEqual(summary["noninferable_cells"], 1)
        self.assertEqual(summary["acc_noninferable"], 1.0)
        self.assertEqual(summary["exact_row_match"], 0.0)

    def test_failed_call_does_not_become_parseable_empty_reply(self):
        archive, dirty, clean, row = self.archive("", n=2)
        rows = self.sc.sample_rows(dirty, clean, archive["summary"])
        archive["trials"] = [
            {"row": rows[0], "output": "", "parsed": False, "error": "APIConnectionError"},
            {"row": rows[1], "output": ",".join(dirty.iloc[rows[1]]), "parsed": True}]
        result = self.sc.rescore_archive(archive, dirty, clean)
        self.assertEqual(result["summary"]["failed_calls"], 1)
        self.assertEqual(result["summary"]["parse_rate"], .5)
        self.assertEqual(result["summary"]["exact_row_match"], .5)
        self.assertEqual(result["counts"]["parsed"], 1)

    def test_malformed_reply_uses_raw_text_not_saved_parsed_or_summary(self):
        archive, dirty, clean, row = self.archive("not a CSV row")
        archive["summary"].update(parse_rate=1.0, hard_cells=900, acc_hard=1.0)
        result = self.sc.rescore_archive(archive, dirty, clean)
        self.assertEqual(result["summary"]["parse_rate"], 0.0)
        self.assertEqual(result["summary"]["hard_cells"], 0)
        self.assertIsNone(result["summary"]["acc_hard"])
        self.assertEqual(result["trial_checks"]["parsed_flag_mismatches"], 1)
        self.assertIn("summary.hard_cells", [x["field"] for x in result["comparison"]["mismatches"]])

    def test_unparseable_trials_contribute_no_cell_denominators(self):
        archive, dirty, clean, row = self.archive("", n=2)
        rows = self.sc.sample_rows(dirty, clean, archive["summary"])
        archive["trials"] = [
            {"row": rows[0], "output": "bad", "parsed": False},
            {"row": rows[1], "output": ",".join(dirty.iloc[rows[1]]), "parsed": True}]
        result = self.sc.rescore_archive(archive, dirty, clean)
        self.assertEqual(result["summary"]["parse_rate"], .5)
        self.assertEqual(result["summary"]["noninferable_cells"], 1)
        self.assertEqual(result["counts"]["unparseable"], 1)

    def test_wrong_trial_rows_rejected_instead_of_using_summary(self):
        archive, dirty, clean, row = self.archive("0,value")
        archive["trials"][0]["row"] = (row + 1) % len(clean)
        with self.assertRaisesRegex(ValueError, "sampling"):
            self.sc.rescore_archive(archive, dirty, clean)

    def test_missing_trials_rejected_without_summary_fallback(self):
        archive, dirty, clean, row = self.archive("0,value")
        archive.pop("trials")
        with self.assertRaisesRegex(ValueError, "trials"):
            self.sc.rescore_archive(archive, dirty, clean)

    def test_dirty_clean_leakage_and_hard_leakage_reconstructed(self):
        archive, dirty, clean, row = self.archive("3,unique-3", error_rows=True)
        self.assertEqual(row, 3)
        result = self.sc.rescore_archive(archive, dirty, clean)
        summary = result["summary"]
        self.assertEqual(summary["acc_hard"], 0.0)
        self.assertEqual(summary["leak_cells"], 1)
        self.assertEqual(summary["leak_rate"], 1.0)
        self.assertEqual(summary["leak_hard_cells"], 1)
        self.assertEqual(summary["leak_hard_rate"], 1.0)

    def test_pure_helpers_never_import_generation_or_loader_modules(self):
        before = set(sys.modules)
        original_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name.endswith(("clients", "probe_rowcont", "data")) or "dotenv" in name:
                raise AssertionError("generation/loader import forbidden")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            helpers = self.sc.pure_helpers(ROOT)
            self.assertEqual(helpers["parse_row"]("```1,2```", 2), ["1", "2"])
        self.assertEqual(set(sys.modules) - before, set())

    def test_changed_counter_helper_is_rejected_before_compilation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "code/src"
            source.mkdir(parents=True)
            (source / "probe_rowcont.py").write_text((ROOT / "code/src/probe_rowcont.py").read_text())
            data = (ROOT / "code/src/data.py").read_text().replace("return cols", "return []")
            (source / "data.py").write_text(data)
            with patch.object(self.sc, "compile", wraps=compile, create=True) as compiler:
                with self.assertRaisesRegex(ValueError, "counter.*AST"):
                    self.sc.pure_helpers(root)
            # The probe may compile; the changed counter function must never do so.
            self.assertEqual(compiler.call_count, 1)

    def test_canonical_counter_helper_allows_unrelated_loader_adaptation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "code/src"
            source.mkdir(parents=True)
            (source / "probe_rowcont.py").write_text((ROOT / "code/src/probe_rowcont.py").read_text())
            # This standalone fixture must not require executing or binding a loader.
            (source / "data.py").write_text((ROOT / "code/src/data.py").read_text() + "\nraise AssertionError('loader executed')\n")
            helpers = self.sc.pure_helpers(root)
            self.assertEqual(helpers["counter_columns"](self.frames()[1]), ["index"])

    def test_counter_ast_provenance_uses_existing_original_source_binding(self):
        manifest = json.loads((ROOT / "data/manifests/CORE_SOURCES.json").read_text())
        self.assertEqual(self.sc.COUNTER_COLUMNS_SOURCE_SHA256,
                         manifest["private_code"]["code/src/data.py"])

    def test_input_hash_and_symlink_mutations_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "input.json"
            path.write_text("original")
            bindings = {"input.json": self.sc.digest(path)}
            path.write_text("changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                self.sc.bound_file(root, "input.json", bindings)
            path.unlink()
            target = root / "target.json"
            target.write_text("original")
            path.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.sc.bound_file(root, "input.json", bindings)

    def test_legacy_failed_calls_omission_is_explicit(self):
        archive, dirty, clean, row = self.archive("0,value")
        actual = self.sc.rescore_archive(archive, dirty, clean)["summary"]
        archive["summary"] = dict(actual)
        archive["summary"].pop("failed_calls")
        result = self.sc.rescore_archive(archive, dirty, clean)
        self.assertEqual(result["comparison"]["mismatches"], [])
        self.assertEqual(result["comparison"]["missing_archived_fields"], ["failed_calls"])

    def test_private_mismatch_details_do_not_export_values_or_column_names(self):
        actual = {"per_column": {"PRIVATE_COLUMN": {"n": 1, "model": .5}}}
        saved = {"per_column": {"PRIVATE_COLUMN": {"n": 1, "model": .8}}}
        result = self.sc.compare_summaries(saved, actual, private=True)
        self.assertNotIn("PRIVATE_COLUMN", json.dumps(result))
        self.assertNotIn("0.8", json.dumps(result))
        self.assertNotIn("0.5", json.dumps(result))
        self.assertTrue(result["mismatches"])

    def test_output_rejects_existing_or_source_nested_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "package"
            root.mkdir()
            private = Path(tmp) / "history"
            private.mkdir()
            for output in (root, root / "data" / "new", private / "new"):
                with self.assertRaises(ValueError):
                    self.sc.validate_output_path(root, output, private)
            allowed = root / "build" / "new"
            self.assertEqual(self.sc.validate_output_path(root, allowed, private), allowed.resolve())

    def test_historical_root_requires_authorization_before_reads(self):
        with self.assertRaisesRegex(ValueError, "together"):
            self.sc.run(ROOT, ROOT / "build" / "unused-test-output", historical_root=ROOT.parent)

    def test_public_inventory_is_complete_and_bound(self):
        paths = self.sc.archive_paths(ROOT)
        self.assertEqual(len(paths), 144)
        self.assertFalse(any("movies" in p.name for p in paths))
        manifest = json.loads((ROOT / "data/manifests/CORE_SOURCES.json").read_text())
        for path in paths:
            self.assertEqual(self.sc.bound_file(ROOT, path.relative_to(ROOT).as_posix(),
                                                manifest["original_files"]), path)

    def test_frozen_helpers_exclude_self_evidence_and_keep_arithmetic(self):
        helpers = self.sc.pure_helpers(ROOT)
        self.assertIsNone(helpers["_top"]({"only": 1}, "only"))
        frame = pd.DataFrame({"id": ["10", "11", "12"], "name": ["a", "b", "c"]})
        base = helpers["structural_baselines"](frame)
        self.assertNotIn("c", helpers["structural_guesses"]("name", frame.iloc[1], frame.iloc[2], base))
        self.assertIn("12", helpers["structural_guesses"]("id", frame.iloc[1], frame.iloc[2], base))

    def test_original_deepseek_summary_mismatch_is_retained(self):
        relative = "artifacts/raw_outputs/p1/custom_deepseek_deepseek-v4-pro__beers__clean__anon.json"
        archive = json.loads((ROOT / relative).read_text())
        clean = pd.read_csv(ROOT / "data/final/beers/clean.csv", dtype=str, keep_default_na=False)
        dirty = pd.read_csv(ROOT / "data/final/beers/dirty.csv", dtype=str, keep_default_na=False)
        dirty.columns = clean.columns
        result = self.sc.rescore_archive(archive, dirty, clean)
        self.assertEqual(archive["summary"]["hard_cells"], 201)
        self.assertEqual(result["summary"]["hard_cells"], 375)
        self.assertEqual(result["summary"]["acc_hard"], .08)
        self.assertTrue(result["comparison"]["mismatches"])
        self.assertEqual(result["trial_checks"]["parsed_flag_mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
