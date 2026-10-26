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

    def test_four_authors_and_current_exact_reading_documents(self):
        citation=(ROOT/'CITATION.cff').read_text()
        self.assertEqual(citation.count('family-names:'),4)
        self.assertIn('duyong@ruc.edu.cn',citation)
        expected={'paper/latex/main.tex':'ba9f2eacdc984c8324f283fb8278f118f0ac2eaac3f29719a8630dcca681e8a9',
                  'paper/latex/main.pdf':'2b6e5fdd814658307f77e1d1da86fa699c574ecd100474a0838598a206ff2e8e',
                  'paper/CoRe-Supplementary-Technical-Report.pdf':'ce23abbc850bcd4ac4df205bddf31d49569423d8e501e75193ae2388914c090c'}
        for name,digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)

if __name__=='__main__':unittest.main()
