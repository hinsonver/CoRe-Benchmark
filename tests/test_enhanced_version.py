"""Additional version binding tests; the original 44 tests remain intact."""
import hashlib
import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class EnhancedVersion(unittest.TestCase):
    def test_all_five_revision_records(self):
        binding = json.loads((ROOT / 'paper/revision-binding.json').read_text())
        self.assertEqual(len(binding['revisions']), 5)
        for row in binding['revisions'].values():
            path = ROOT / row['packaged_record']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['record_sha256'])
    def test_all_package_bindings(self):
        binding = json.loads((ROOT / 'paper/revision-binding.json').read_text())
        for name, expected in binding['package_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)
    def test_current_manuscript_version(self):
        self.assertEqual(hashlib.sha256((ROOT / 'paper/latex/main.tex').read_bytes()).hexdigest(),
                         'f6dd7854942a0fb405636b2f708b30fad233e8efe35526386af16506fef32ca0')
    def test_new_historical_archive_binding(self):
        metadata = json.loads((ROOT / 'data/manifests/SUBMISSION_DATA.json').read_text())
        self.assertEqual(metadata['historical']['archive_filename'],
                         'CoRe-submission-VE-M01-M05-historical.zip')
    def test_overview_and_dataset_navigation_scope(self):
        mapping = json.loads((ROOT / 'paper/result-map.json').read_text())
        binding = json.loads((ROOT / 'paper/revision-binding.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT / binding['compiled_navigation_aux']).read_bytes()).hexdigest(),
                         binding['source_sha256']['论文/latex/main.aux'])
        for row in mapping['entries']:
            if row['label'] in {'fig:overview', 'tab:datasets'}:
                self.assertEqual(row['claims'], ['C1', 'C2', 'C3'])
