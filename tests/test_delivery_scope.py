"""Contract for the integrated delivery, distinct from scientific agreement."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class DeliveryScope(unittest.TestCase):
    def test_complete_route_inventory(self):
        path=ROOT/'REPRODUCTION.json'
        self.assertTrue(path.is_file(), 'Unified experiment coverage matrix is missing')
        data=json.loads(path.read_text())
        self.assertEqual(data['schema_version'],1)
        expected={'continuation','four-condition-cleaning','construction-seeds','scale',
                  'aligned','whole-table-baran','tabclean','knowledge-conflicts',
                  'reference-audit','archived-diagnostics','construction-provenance'}
        self.assertEqual({r['id'] for r in data['routes']},expected)
        for row in data['routes']:
            self.assertTrue(row['input_acquisition'])
            self.assertTrue(row['execution']['command'])
            self.assertTrue(row['scoring']['command'])
            self.assertTrue(row['display'])
            self.assertIsInstance(row['historical_limits'],list)

    def test_historical_limits_are_not_erased(self):
        path=ROOT/'REPRODUCTION.json'
        self.assertTrue(path.is_file(),'Explicit historical boundaries are missing')
        data=json.loads(path.read_text())
        self.assertEqual(data['readiness']['official_eligibility'],'not_determined')
        self.assertFalse(data['readiness']['actual_review_access_ready'])
        self.assertEqual(data['known_limits']['continuation']['full_mismatch_archives'],12)
        self.assertEqual(data['known_limits']['whole_table_baran']['count_only_runs'],12)
        self.assertFalse(data['known_limits']['reference_audit']['complete_historical_candidate_payloads'])

    def test_display_navigation_has_real_targets(self):
        data=json.loads((ROOT/'REPRODUCTION.json').read_text())
        labels={r['label'] for r in json.loads((ROOT/'paper/result-map.json').read_text())['entries']}
        for row in data['routes']:
            for target in row['display']:
                if target.startswith(('fig:','tab:')):
                    self.assertIn(target,labels)
                elif target.startswith('results/'):
                    self.assertTrue((ROOT/target).is_file())

    def test_original_frozen_reference_files_present(self):
        directory=ROOT/'data/reference/frozen-tables'
        self.assertEqual(len(list(directory.glob('*.tex'))),15)
        self.assertEqual(hashlib.sha256((directory/'p1.tex').read_bytes()).hexdigest(),
                         '2d024ba4f49c2743048a481e171b95c8b469c9ce5ada6fad2f8d5367939d1882')

    def test_five_authors_and_current_exact_reading_documents(self):
        citation=(ROOT/'CITATION.cff').read_text()
        self.assertEqual(citation.count('family-names:'),5)
        self.assertIn('duyong@ruc.edu.cn',citation)
        expected={'paper/latex/main.tex':'542b17bc9e4bf9b8b39dc5cfab4fe1b9a0f224f3b721374f9b4c48b6610c1a43',
                  'paper/latex/main.pdf':'1758dbf40f1ac06751c84b45891b0bf9a637fdbc3e37942e615ef77f2fe5d883',
                  'paper/CoRe-Supplementary-Technical-Report.pdf':'51bf5fb9bc315b35d5620765de7083049857bb3a90b7c1dff51107f82d922adc'}
        for name,digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)

if __name__=='__main__':unittest.main()
