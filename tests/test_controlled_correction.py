"""Current-only correction; historical source and frozen products stay intact."""
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'code')]


class ControlledCorrection(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('src.uniform_continuation'),
                             'Uniform integer derivative loader is missing')
        return importlib.import_module('src.uniform_continuation')

    def test_current_p1_uses_exact_uniform_counts(self):
        tables = importlib.import_module('src.paper_tables')
        with tempfile.TemporaryDirectory() as tmp:
            old = tables.TEX
            try:
                tables.TEX = Path(tmp)
                tables.p1_table()
            finally:
                tables.TEX = old
            text = (Path(tmp) / 'p1.tex').read_text()
            self.assertIn('DeepSeek-V4-Pro & 0.080 & 0.070 & 0.085 & 0.065 & --- & 3 / 601', text)
            self.assertIn('OLMo-2-7B (base) & 0.011', text)

    def test_current_beers_holm_uses_exact_sign_counts(self):
        tables = importlib.import_module('src.paper_tables')
        with tempfile.TemporaryDirectory() as tmp:
            old = tables.TEX
            try:
                tables.TEX = Path(tmp)
                tables.beers_table()
            finally:
                tables.TEX = old
            text = (Path(tmp) / 'beers.tex').read_text()
            rows = [line for line in text.splitlines() if line.strip().startswith(('DeepSeek-', 'Qwen3.8-'))]
            self.assertTrue(rows[0].endswith('0.646 ' + r'\\'), rows[0])
            self.assertTrue(rows[1].endswith('0.154 ' + r'\\'), rows[1])

    def test_all_168_archives_and_integer_argmax_are_bound(self):
        module = self.module()
        payload = module.load_uniform(ROOT)
        self.assertEqual(len(payload['archives']), 168)
        self.assertEqual(sum(a['summary']['n'] for a in payload['archives']), 9600)
        rows = module.current_rows(ROOT)
        deepseek = rows['custom_deepseek_deepseek-v4-pro']
        self.assertEqual(deepseek['max_counts'][:3], [[30, 375], [14, 200], [32, 375]])
        self.assertEqual(deepseek['hard_leak'], [3, 601])
        self.assertEqual(len(rows), 7)
        self.assertEqual(sum(rows[tag]['hard_leak'][0] for tag in rows if tag.startswith('local_qwen') or tag == 'local_llama3.1-8b'), 1)
        self.assertEqual(sum(rows[tag]['hard_leak'][1] for tag in rows if tag.startswith('local_qwen') or tag == 'local_llama3.1-8b'), 2008)

    def test_count_tamper_missing_model_and_empty_coverage_fail_closed(self):
        module = self.module()
        payload = module.load_uniform(ROOT)
        mutations = []
        changed = copy.deepcopy(payload)
        changed['archives'][0]['counts']['hard'][0] += 1
        mutations.append(changed)
        changed = copy.deepcopy(payload)
        changed['archives'] = [a for a in changed['archives'] if a['summary']['model'] != 'local:qwen2.5-7b']
        mutations.append(changed)
        changed = copy.deepcopy(payload)
        changed['archives'] = []
        mutations.append(changed)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'derivative.json'
            for changed in mutations:
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    module.load_uniform(ROOT, data_path=path)

    def test_original_archive_tamper_fails_even_with_bound_derivative(self):
        module = self.module()
        payload = module.load_uniform(ROOT)
        record = next(a for a in payload['archives'] if 'movies' not in a['archive'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / record['archive']
            source.parent.mkdir(parents=True)
            source.write_bytes((ROOT / record['archive']).read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                module.verify_source(root, record['archive'], record['archive_sha256'])

    def test_public_derivative_has_only_aggregate_movie_payload(self):
        module = self.module()
        payload = module.load_uniform(ROOT)
        from src.core_runtime import check_payload
        check_payload(payload)
        for archive in payload['archives']:
            self.assertEqual(set(archive), {'archive', 'archive_sha256', 'summary', 'counts', 'per_column_integer_counts'})
        self.assertEqual(payload['method']['criterion'], 'current_full')
        self.assertFalse(payload['method']['strict_row_refit'])
        self.assertEqual(payload['method']['fd_admission'], {'max_unique_fraction': 0.5, 'min_modal_mapping_coverage': 0.99, 'fit': 'full_table'})
        self.assertEqual(payload['method']['leakage_context'], 'clean_full_table_and_clean_predecessor')


if __name__ == '__main__':
    unittest.main()
