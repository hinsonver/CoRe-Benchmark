"""Tests written before the new diagnostic implementation."""
from pathlib import Path
import importlib.util
import unittest
import tempfile
import json
import zipfile
import hashlib

class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).with_name('diagnostics.py')
        self.assertTrue(path.exists(),'The diagnostic implementation does not yet exist')
        spec=importlib.util.spec_from_file_location('diag',path)
        self.d=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.d)
    def test_graph_connected_through_repeated_entity(self):
        a=self.d.incidence([['a','b'],['b','c'],['d']])
        self.assertEqual(a['components'],2)
        self.assertEqual(a['max_replies_per_entity'],2)
        self.assertEqual(a['entities'],4)
    def test_graph_rejects_duplicate_entities_within_main_chunk(self):
        with self.assertRaises(ValueError):self.d.incidence([['a','a']],unique=True)
    def test_target_rows_are_not_independent_replies(self):
        a=self.d.incidence([['a','a','a','b','b','b']],unique=False)
        self.assertEqual(a['max_replies_per_entity'],1)
        self.assertEqual(a['entities'],2)
        self.assertEqual(a['max_entities_per_reply'],2)
    def test_f1_is_pooled_count_ratio(self):
        self.assertAlmostEqual(self.d.f1({'errors':8,'predicted':2,'repaired':2}),.4)
        self.assertEqual(self.d.f1({'errors':0,'predicted':0,'repaired':0}),0)
    def test_delete_group_preserves_false_positive_counts(self):
        a=self.d.subtract({'errors':4,'predicted':5,'repaired':3},
                          {'errors':0,'predicted':1,'repaired':0})
        self.assertEqual(a,{'errors':4,'predicted':4,'repaired':3})
        self.assertEqual(self.d.f1(a),.75)
    def test_delete_group_rejects_negative_counts(self):
        with self.assertRaises(ValueError):self.d.subtract({'errors':0},{'errors':1})
    def test_year_unchanged_is_not_a_selected_candidate(self):
        self.assertEqual(self.d.year_choice('2014 2015 2016','2014 2015 2016'),'unchanged')
    def test_year_reference_need_not_be_middle(self):
        self.assertEqual(self.d.year_choice('2014 2015 2016','2014'),'first')
        self.assertEqual(self.d.year_choice('2014 2015 2016','2017'),'other')
        self.assertEqual(self.d.year_choice('2014 2015 2016','2015'),'middle')
    def test_noop_after_effective_edit_does_not_erase_it(self):
        edits=self.d.effective([['old']],['x'],[{'row':1,'column':'x','value':'new'},
                                               {'row':1,'column':'x','value':'old'}])
        self.assertEqual(edits,{(0,'x'):'new'})
    def test_year_requires_three_candidates(self):
        with self.assertRaises(ValueError):self.d.year_choice('2015','2015')
    def test_bound_private_original_precedes_public_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';(repo/'data/manifests').mkdir(parents=True)
            rel='summary.json';original=b'{"raw":true}'
            (repo/rel).write_text('{"projection":true}')
            (repo/'data/manifests/CORE_SOURCES.json').write_text(json.dumps(
                {'private_files':{rel:hashlib.sha256(original).hexdigest()}}))
            archive=root/'history.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr(rel,original)
            self.assertEqual(self.d.Sources(repo,archive).json(rel),{'raw':True})

if __name__=='__main__':unittest.main()
