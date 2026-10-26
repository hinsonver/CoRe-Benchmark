"""Fast safety and reporting contracts for the single offline entry point."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / 'tools/reproduce_all.py'


class AllReproductionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENTRY.is_file(), 'unified offline entry is not implemented')
        spec = importlib.util.spec_from_file_location('reproduce_all', ENTRY)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_output_refuses_reuse_source_ancestor_and_source_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'package'
            root.mkdir()
            for output in (root, root.parent, root / 'tools/new'):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    self.mod.validate_output(root, output)
            self.assertEqual(self.mod.validate_output(root, root / 'build/new'), root / 'build/new')

    def test_output_rejects_symlink_parent_and_history_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            root = base / 'package'
            root.mkdir()
            history = base / 'history'
            history.mkdir()
            link = base / 'link'
            link.symlink_to(history, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                self.mod.validate_output(root, link / 'new')
            with self.assertRaisesRegex(ValueError, 'historical'):
                self.mod.validate_output(root, history / 'new', history)

    def test_matrix_requires_unique_named_routes_and_commands(self):
        route = {'id': 'raw', 'execution': {'command': 'offline execute'}, 'scoring': {'command': 'offline score'}}
        self.assertEqual(len(self.mod.validate_matrix({'schema_version': 1, 'routes': [route]})['routes']), 1)
        for value in ({'schema_version': 2, 'routes': [route]}, {'schema_version': 1, 'routes': [route, route]},
                      {'schema_version': 1, 'routes': [{'id': 'bad'}]}):
            with self.assertRaises(ValueError):
                self.mod.validate_matrix(value)

    def test_manifest_check_rejects_changed_bytes_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'a.txt').write_text('original')
            digest = self.mod.digest(root / 'a.txt')
            (root / 'MANIFEST.sha256').write_text(digest + '  a.txt\n')
            self.assertEqual(self.mod.verify_manifest(root)['files'], 1)
            (root / 'a.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'hash'):
                self.mod.verify_manifest(root)

    def test_comparison_checks_actual_bytes_and_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ref, got = base / 'ref', base / 'got'
            ref.mkdir()
            got.mkdir()
            (ref / 'a.tex').write_text('exact')
            (got / 'a.tex').write_text('exact')
            self.assertTrue(self.mod.compare_products(ref, got, '*.tex', 1)['byte_identical'])
            (got / 'a.tex').write_text('different')
            self.assertFalse(self.mod.compare_products(ref, got, '*.tex', 1)['byte_identical'])
            (got / 'extra.tex').write_text('extra')
            self.assertFalse(self.mod.compare_products(ref, got, '*.tex', 1)['inventory_equal'])

    def test_expected_discrepancy_requires_complete_report(self):
        complete = {'schema_version': 1, 'mode': 'saved_raw_trial_rejudgment', 'new_model_calls': 0,
                    'summary_fallback': False, 'included_archives': 1, 'historical_movie_archives': 0,
                    'trials': 1, 'summary_mismatch_archives': 1, 'parsed_flag_mismatches': 0,
                    'archives': [{'trial_checks': {'trials': 1}, 'comparison': {'mismatches': ['different']}}]}
        self.assertFalse(self.mod.expected_discrepancy('continuations', 1, complete))
        self.assertFalse(self.mod.expected_discrepancy('continuations', 1, {}))
        self.assertFalse(self.mod.expected_discrepancy('rayyan', 1, complete))
        self.assertFalse(self.mod.expected_discrepancy('continuations', 2, complete))

    def test_zero_coverage_complete_looking_baseline_is_rejected(self):
        report = {'schema_version': 1, 'mode': 'public_raw_only',
                  'no_generation_training_or_network_calls': True, 'frozen_results_modified': False,
                  'coverage': dict.fromkeys(('tabclean_raw_conditions', 'e5_raw_runs', 'e5_count_only_runs',
                                             'aligned_raw_archives'), 0),
                  'differences': [], 'tabclean': {}, 'whole_table_baran': {}, 'aligned': {}}
        self.assertFalse(self.mod.complete_scoring_report('baselines', report))

    def test_arbitrary_selected_baseline_difference_is_not_expected(self):
        report = {'schema_version': 1, 'mode': 'public_raw_only',
                  'no_generation_training_or_network_calls': True, 'frozen_results_modified': False,
                  'coverage': {'tabclean_raw_conditions': 9, 'e5_raw_runs': 42, 'e5_count_only_runs': 12,
                               'aligned_raw_archives': 40, 'aligned_archives_inspected': 40,
                               'aligned_historical_metadata_mismatches': []},
                  'differences': [{'location': 'e4/hospital/all/repair_f1', 'reconstructed': 0.0, 'archived': 1.0}],
                  'tabclean': {str(i): {} for i in range(9)},
                  'whole_table_baran': {str(i): {} for i in range(54)},
                  'aligned': {str(i): {} for i in range(40)}}
        self.assertFalse(self.mod.expected_discrepancy('baselines', 2, report))

    def test_claimed_full_continuation_counts_without_bound_identities_fail(self):
        archives = [{'archive': 'invented-' + str(i), 'trial_checks': {'trials': 50},
                     'comparison': {'mismatches': []}} for i in range(144)]
        archives[-1]['trial_checks']['trials'] += 1000
        report = {'schema_version': 1, 'mode': 'saved_raw_trial_rejudgment', 'new_model_calls': 0,
                  'summary_fallback': False, 'included_archives': 144, 'historical_movie_archives': 0,
                  'trials': 8200, 'summary_mismatch_archives': 0, 'parsed_flag_mismatches': 0,
                  'archives': archives}
        self.assertFalse(self.mod.complete_scoring_report('continuations', report))

    def test_matrix_current_csv_reference_key_is_consumed(self):
        matrix = {'references': {'current_csvs': 'custom/current-csvs'}}
        self.assertEqual(self.mod.product_reference(ROOT, matrix, 'current_csvs', 'results/figures'),
                         ROOT / 'custom/current-csvs')

    def test_environment_drops_core_redirects_credentials_and_python_injection(self):
        env = self.mod.clean_environment(ROOT, {'CORE_MODE': 'authorized', 'CORE_PRIVATE_ROOT': '/secret',
                                               'OPENAI_API_KEY': 'secret', 'PYTHONPATH': '/evil', 'PATH': '/bin'})
        self.assertEqual(env['CORE_MODE'], 'public')
        self.assertNotIn('CORE_PRIVATE_ROOT', env)
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('/evil', env['PYTHONPATH'])

    def test_guard_rejects_network_dotenv_and_model_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = self.mod.write_guard(Path(tmp))
            env = self.mod.clean_environment(ROOT)
            env['PYTHONPATH'] = str(guard) + os.pathsep + env['PYTHONPATH']
            for code in ('import socket; socket.create_connection(("example.com",443))',
                         'import openai', 'open(".env")',
                         'from src.clients import complete; complete("mock:echo", "x")'):
                result = subprocess.run([sys.executable, '-B', '-c', code], cwd=tmp, env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, code)
                self.assertIn('offline', result.stderr.lower())
            result = subprocess.run([sys.executable, '-B', '-c',
                                     'from src.clients import truncated; assert truncated("{") and not truncated("{}")'],
                                    cwd=tmp, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_guard_survives_grandchild_pythonpath_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = self.mod.write_guard(Path(tmp))
            env = self.mod.clean_environment(ROOT)
            env['PYTHONPATH'] = str(guard) + os.pathsep + env['PYTHONPATH']
            grandchild = 'import socket; socket.getaddrinfo("example.com",443)'
            code = ('import os,subprocess,sys; e=dict(os.environ); e["PYTHONPATH"]=""; '
                    'p=subprocess.run([sys.executable,"-c",' + repr(grandchild) + '],'
                    'env=e,capture_output=True,text=True); '
                    'assert p.returncode!=0 and "Offline" in p.stderr')
            result = subprocess.run([sys.executable, '-B', '-c', code], cwd=tmp, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_child_failure_without_report_is_not_scientific_discrepancy(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            record, report = self.mod.run_child('continuations', [sys.executable, '-B', '-c', 'raise RuntimeError("unexpected")'],
                                                ROOT, output, self.mod.clean_environment(ROOT), output / 'missing.json')
            self.assertFalse(record['execution_completed'])
            self.assertFalse(record['expected_scientific_discrepancy'])
            self.assertIsNone(report)
            self.assertIn('unexpected', (output / record['stderr']).read_text())
            self.assertEqual(json.loads((output / 'commands/continuations/command.json').read_text())['returncode'], 1)

    def test_nonobject_child_report_still_produces_failure_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            child = output / 'child.json'
            child.write_text('[]')
            report = {'commands': [], 'errors': ['unexpected child failure'], 'historical_requested': False,
                      'child_reports': {'continuations': {'path': 'child.json', 'sha256': self.mod.digest(child)}}}
            self.mod.finalize(report, output)
            self.assertEqual(report['exit_code'], 1)
            self.assertFalse(report['technical_execution_completed'])
            self.assertTrue((output / 'coverage.json').is_file())

    def test_cli_requires_explicit_output_and_paired_history_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'new'
            for args in ([], ['--output', str(output), '--historical-root', tmp]):
                result = subprocess.run([sys.executable, '-B', str(ENTRY), *args], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_cli_never_overwrites_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'keep'
            marker.write_text('unchanged')
            result = subprocess.run([sys.executable, '-B', str(ENTRY), '--output', tmp], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(), 'unchanged')


if __name__ == '__main__':
    unittest.main()
