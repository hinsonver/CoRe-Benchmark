"""Executable contract for the current manuscript and formal report (offline only)."""
import csv
import hashlib
import importlib
import json
from pathlib import Path
import re
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'code')]
MAIN_SHA = 'ba9f2eacdc984c8324f283fb8278f118f0ac2eaac3f29719a8630dcca681e8a9'
PDF_SHA = '2b6e5fdd814658307f77e1d1da86fa699c574ecd100474a0838598a206ff2e8e'


class CurrentRevision(unittest.TestCase):
    def test_exact_adopted_manuscript_and_navigation(self):
        for name, expected in [('main.tex', MAIN_SHA), ('main.pdf', PDF_SHA)]:
            self.assertEqual(hashlib.sha256((ROOT / 'paper/latex' / name).read_bytes()).hexdigest(), expected)
        text = (ROOT / 'paper/latex/main.tex').read_text()
        expanded = re.sub(r'\\input\{(tables/[^}]+)\}',
                          lambda m: (ROOT / 'paper/latex' / (m[1] + '.tex')).read_text(), text)
        self.assertEqual(len(re.findall(r'\\begin\{figure\*?\}', expanded)), 8)
        self.assertEqual(len(re.findall(r'\\begin\{table\*?\}', expanded)), 17)
        self.assertEqual(len(re.findall(r'\\label\{find:', text)), 7)
        self.assertEqual(len(list((ROOT / 'paper/companions').glob('[0-9][0-9]-*.md'))), 0)
        self.assertEqual(hashlib.sha256((ROOT / 'paper/CoRe-Supplementary-Technical-Report.pdf').read_bytes()).hexdigest(),
                         'ce23abbc850bcd4ac4df205bddf31d49569423d8e501e75193ae2388914c090c')
        self.assertEqual(len(list((ROOT / 'results/figures').glob('*.csv'))), 11)

    def test_current_display_projects_19_tables_exactly(self):
        from tools.submission_display import apply_current_display
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            shutil.copytree(ROOT / 'results/tables', output / 'tables')
            result = apply_current_display(ROOT, output)
            self.assertEqual(result['table_source_count'], 19)
            self.assertIn(r'\multicolumn{4}{c}{Scores} & Nonpaired',
                          (output / 'tables/decomposition.tex').read_text())
            self.assertIn('repaired cities (O/F/W/S, of 127)',
                          (output / 'tables/beers.tex').read_text())
            self.assertIn('separate eight-model Holm families by dataset',
                          (output / 'tables/counts.tex').read_text())
            for table in (ROOT / 'paper/latex/tables').glob('*.tex'):
                self.assertEqual((output / 'tables' / table.name).read_bytes(), table.read_bytes(), table.name)
            # A second projection is safe; numeric-body tampering is never accepted.
            apply_current_display(ROOT, output)
            table = output / 'tables/decomposition.tex'
            table.write_text(table.read_text().replace('DeepSeek-V4-Pro', 'Changed-model', 1))
            with self.assertRaisesRegex(ValueError, 'frozen non-caption'):
                apply_current_display(ROOT, output)

    def test_three_figures_replay_source_cells_and_numbers(self):
        for name in ('example_diagrams', 'evidence_panels'):
            self.assertTrue((ROOT / 'code/src' / (name + '.py')).is_file(), name + ' replay helper missing')
        examples = importlib.import_module('src.example_diagrams')
        recovery = importlib.import_module('src.evidence_panels')
        with (ROOT / 'results/figures/fig0_overview.csv').open(newline='') as handle:
            expected = list(csv.DictReader(handle))
        actual = [{k: str(v) for k, v in row.items()} for row in examples.overview_rows()]
        self.assertEqual(actual, expected)
        with (ROOT / 'results/figures/fig_example_transfer.csv').open(newline='') as handle:
            expected = list(csv.DictReader(handle))
        self.assertEqual([{k: str(v) for k, v in row.items()} for row in examples.construction_rows()], expected)
        with (ROOT / 'results/figures/fig1_recovery_evidence.csv').open(newline='') as handle:
            expected = list(csv.DictReader(handle))
        actual = [{k: str(v) for k, v in row.items()} for row in recovery.recovery_rows()]
        self.assertEqual(actual, expected)
        with tempfile.TemporaryDirectory() as tmp:
            for function, stem in [(examples.render_overview, 'fig0_overview'),
                                   (examples.render_construction, 'fig_example_transfer'),
                                   (recovery.render_recovery_evidence, 'fig1_recovery_evidence')]:
                drawing = function(Path(tmp))
                self.assertTrue(drawing.rows)
                for ext in ('pdf', 'png', 'svg', 'csv'):
                    self.assertGreater((Path(tmp) / (stem + '.' + ext)).stat().st_size, 100)
                import matplotlib.pyplot as plt
                plt.close(drawing.figure)

    def diagnostic_module(self):
        self.assertTrue((ROOT / 'tools/review_diagnostics.py').is_file(), 'offline diagnostic replay missing')
        return importlib.import_module('tools.review_diagnostics')

    def test_review_diagnostic_recomputes_bound_scope(self):
        result = self.diagnostic_module().replay(ROOT)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['families']['changed_positions'], [13, 14])
        self.assertEqual(result['families']['sensitivity'][13]['n'], [50, 49])
        self.assertEqual(result['families']['sensitivity'][14]['n'], [48, 48])
        self.assertEqual(result['rayyan']['matched'], 152)
        encoding = result['rayyan']['strata'][1]
        self.assertEqual(encoding['dirty_assessment'], 'unassessed')
        self.assertIsNone(encoding['dirty_agrees_assessed'])
        self.assertEqual(result['hospital']['words'][0]['passes_8pp'], False)
        self.assertEqual(result['capability']['raw_movie_reply_rescoring'], False)
        self.assertEqual(result['capability']['usage_log_replay'], False)
        self.assertEqual(result['capability']['truncation_detection_replayed'], False)
        self.assertEqual(result['capability']['historical_source_bindings_checked'], False)
        self.assertEqual(result.get('aggregate_only', {}).get('rating_count', {}).get('conditions', [{}])[0].get('noops'), 73)
        self.assertEqual(result.get('aggregate_only', {}).get('usage', {}).get('totals', {}).get('input_plus_output'), 26605538)

    def test_diagnostics_never_import_model_clients(self):
        code = ('import sys; from tools.review_diagnostics import replay; '
                'replay(); assert "src.clients" not in sys.modules; '
                'assert "openai" not in sys.modules; assert "dotenv" not in sys.modules')
        subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, check=True,
                       env={**os.environ, 'CORE_MODE': 'public', 'PYTHONDONTWRITEBYTECODE': '1'})

    def test_legacy_private_namespace_and_frozen_scorer_are_unchanged(self):
        expected = {
            'code/src/paper_tables_frozen.py': 'ca0385dfef035808c9d216da1776a65d6f6954a26719cab29a534e3a83257b7f',
            'code/src/core_runtime.py': '6df64bfc044cb398b44128f75f5c809f1349b114a6c337b6bd3d01e2c47dba07',
            'tools/submission_history.py': 'e2423a8379bfe12cce3abb4a2711c59829810bc88767ec91c5a99b755e7177eb',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)

    def test_all_15_original_frozen_tables_replay_exactly(self):
        # Hashes are from the retained original CoRe-public-candidate 15 tables,
        # not from the newer caption/display projection.
        expected = {
            'aligned.tex': 'fcd7119199044d4d77d364951908e1220924452a98843c5926f2e5c19c3b7a48',
            'beers.tex': 'ee2323ee5d0a1f57227fc9289e557b624a6542071ab8eb87faa8e3647d7e79e4',
            'checks.tex': 'bdeae7ad8ddbfb62b97bb3c79e525f7194787e21d08c9130098d67db7b66b5f9',
            'construction.tex': 'd73772be701e7ff70417e3bf958daa9068bb7ff59f4c757b45645436944230f9',
            'counts.tex': '02f7e3f02f148fd183904087f4e1734d9ce152cce7b0c3520e204680a83030dc',
            'decoding.tex': 'cb4132edc4622af995e791d5114ffbb223063d62ceef471a36e4e298aa7868f8',
            'decomposition.tex': '9dac92e2b0c64a69ff827b799dba11678a352001f31a620c01068f4fbffa4695',
            'detection.tex': '16f677c692170fb6fb0ee1ebaffcfd70ae6bc75df8a1d1fbfc4bd065c92997b3',
            'example.tex': 'e6cc2f14281ca44671293d8692c3f32a0e46520964a3a27c1c8e6da69f3c5b9a',
            'moviescols.tex': '06d7482c27baff93b293fff42c32a26d1023232ad853fa895867c65ac1743124',
            'movieserrors.tex': '6a706774ecba7dda6254fe0042c1bfb0a859537c95c14eb1da1e49ea2ae172c8',
            'near.tex': '31bdb1545c8a4526466c479186fd3addee4e83e38dd868e9af0601fc63ff25e6',
            'p1.tex': '2d024ba4f49c2743048a481e171b95c8b469c9ce5ada6fad2f8d5367939d1882',
            'rayyan.tex': 'eb68e9fb012bdcc07ce0489d49f4bf9a413d9037b3a7df62ffbbc11069b32f60',
            'seeds.tex': '9c6d6bfee11457f43f58988477fc7e1cbd05d8552f41052283ff8ccada61711c',
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            env = {**os.environ, 'CORE_MODE': 'public', 'CORE_ARTIFACT_ROOT': str(ROOT),
                   'CORE_TABLE_DIR': str(output), 'PYTHONPATH': str(ROOT / 'code'),
                   'PYTHONDONTWRITEBYTECODE': '1'}
            subprocess.run([sys.executable, '-B', '-m', 'src.paper_tables_frozen'],
                           cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
            self.assertEqual({p.name for p in output.glob('*.tex')}, set(expected))
            for name, digest in expected.items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest, name)

    def test_diagnostics_fail_closed_on_missing_or_tampered_evidence(self):
        module = self.diagnostic_module()
        with tempfile.TemporaryDirectory() as tmp:
            aggregate = Path(tmp) / 'aggregate.json'
            with self.assertRaises(FileNotFoundError):
                module.replay(ROOT, aggregate_path=aggregate)
            aggregate.write_bytes((ROOT / 'results/derived/review_diagnostics.json').read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'aggregate hash'):
                module.replay(ROOT, aggregate_path=aggregate)
            aggregate.write_bytes((ROOT / 'results/derived/review_diagnostics.json').read_bytes())
            with self.assertRaises(FileNotFoundError):
                module.replay(Path(tmp), aggregate_path=aggregate)
            (Path(tmp) / 'data/manifests').mkdir(parents=True)
            (Path(tmp) / 'data/witnesses').mkdir()
            shutil.copyfile(ROOT / 'data/manifests/CORE_WITNESSES.json',
                            Path(tmp) / 'data/manifests/CORE_WITNESSES.json')
            witness = Path(tmp) / 'data/witnesses/movies.json'
            witness.write_bytes((ROOT / 'data/witnesses/movies.json').read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'witness hash mismatch'):
                module.replay(Path(tmp), aggregate_path=aggregate)


if __name__ == '__main__':
    unittest.main()
