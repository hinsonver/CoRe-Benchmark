import importlib.util
from pathlib import Path
import tempfile
import unittest
HERE = Path(__file__).resolve().parents[1]

class HistoricalOverlayTests(unittest.TestCase):
    def test_historical_overlay_has_only_hash_bound_original_scoring_modules(self):
        entry = HERE / 'tools/submission_history.py'
        self.assertTrue(entry.is_file(),'historical scoring namespace isolation is not implemented')
        spec = importlib.util.spec_from_file_location('submission_history',entry)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='core-original-namespace-') as tmp:
            overlay = Path(tmp)
            (overlay / 'code/src').mkdir(parents=True)
            for name in ['__init__.py','original_scorer.py','paper_presentation.py','core_runtime.py']:
                (overlay / 'code/src' / name).write_text('# fixture\n')
            (overlay / 'code/src/keep.json').write_text('{}')
            original = {'code/src/__init__.py':'bound-init','code/src/original_scorer.py':'bound-scorer'}
            removed = module.restrict_scoring_modules(overlay,original)
            self.assertEqual(set(removed),{'code/src/paper_presentation.py','code/src/core_runtime.py'})
            self.assertEqual({p.name for p in (overlay / 'code/src').iterdir()},
                             {'__init__.py','original_scorer.py','keep.json'})

