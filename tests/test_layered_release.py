"""A04 public-tree contract, including failure paths; standard library only."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from src import scope_runtime as scoped


def tool(name):
    spec=importlib.util.spec_from_file_location('a04_'+name,ROOT/'tools'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class LayeredRelease(unittest.TestCase):
    def test_original_paths_absent_and_external_manifest_exact(self):
        s=scoped.source_manifest(ROOT)
        self.assertEqual(len(s['controlled_files']),138)
        self.assertTrue(all(not(ROOT/p).exists() for p in s['controlled_files']))
        core=json.loads((ROOT/'data/manifests/CORE_SOURCES.json').read_text())
        self.assertEqual(len(core['private_files']),402)
        self.assertEqual(len(core['private_code']),25)
        self.assertEqual(len(s['public_identical_bytes']),7)
        for n,item in s['public_identical_bytes'].items():
            self.assertNotIn(item['public_path'],s['controlled_files'])
            self.assertEqual(hashlib.sha256((ROOT/item['public_path']).read_bytes()).hexdigest(),s['controlled_files'][n])

    def test_anonymous_witness_schema(self):
        value=scoped.read_scope(ROOT);scoped.check_numeric_payload(value)
        self.assertEqual(len(value['near']),6)
        self.assertEqual(len(value['source_sha256']),len({**scoped.source_manifest(ROOT)['controlled_files'],
            **scoped.source_manifest(ROOT)['export_dependencies']}))

    def test_counts_and_denominators_are_recomputed(self):
        result=scoped.verify_scope(ROOT)
        self.assertEqual(result['controlled_original_paths_absent'],138)
        for record in scoped.read_scope(ROOT)['near'].values():
            self.assertEqual(scoped.known_rates_from_record(record),record['summary']['key_rates_known'])

    def test_nested_raw_fields_rejected(self):
        for name in ['answer','output','examples','fixes','truth','famous']:
            with self.assertRaises(ValueError):scoped.check_numeric_payload({'nested':[{name:'record'}]})

    def test_changed_known_flags_rejected(self):
        record=copy.deepcopy(next(iter(scoped.read_scope(ROOT)['near'].values())))
        record['events'][0]['known']=not record['events'][0]['known']
        with self.assertRaises(ValueError):scoped.known_rates_from_record(record)

    def test_impossible_and_duplicate_cell_flags_rejected(self):
        cell=copy.deepcopy(scoped.read_scope(ROOT)['rayyan']['cells'][0])
        with self.assertRaises(ValueError):scoped.rayyan_counts([cell,cell],set())
        cell.update(error=False,changed=False,repaired=True)
        with self.assertRaises(ValueError):scoped.rayyan_counts([cell],set())

    def test_witness_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'data/witnesses').mkdir(parents=True);(root/'data/manifests').mkdir()
            p=root/'data/witnesses/scoped.json';p.write_text('{"schema_version":1}')
            (root/'data/manifests/SCOPE_WITNESSES.json').write_text(json.dumps({'files':{
                'data/witnesses/scoped.json':'0'*64}}))
            with self.assertRaises(ValueError):scoped.read_scope(root)

    def test_fixed_input_route_is_opt_in_and_external(self):
        acquire=tool('acquire_inputs')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();dest=root.parent/(root.name+'-not-created')
            with self.assertRaises(ValueError):acquire.fetch('rayyan-inputs',dest,False,root)
            self.assertFalse(dest.exists())
            with self.assertRaises(ValueError):acquire.validate_destination(root,root/'inside')
        self.assertEqual(set(acquire.ASSETS),{'rayyan-inputs'})
        self.assertTrue(all('/ae292b6ff8118c8786cd7c97364e9a8a07f00b62/datasets/rayyan/' in x['url']
            for x in acquire.ASSETS['rayyan-inputs'].values()))

    def test_licenses_are_bound_and_template_source_present(self):
        binding=json.loads((ROOT/'data/manifests/LICENSE_SOURCES.json').read_text())
        self.assertEqual(len(binding['sources']),6)
        for name,row in binding['sources'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),row['packaged_sha256'])
        for text in ['THIRD_PARTY_NOTICES.md','LICENSES/Beers-NOTICE.md','LICENSES/Models-NOTICE.md']:
            self.assertTrue((ROOT/text).is_file())

    def test_public_rayyan_reports_recount_not_raw_scoring(self):
        from src.rayyan_replay import replay
        r=replay(ROOT)
        self.assertFalse(r['delivery_verification']['public_raw_tabclean_rescoring'])
        self.assertEqual(r['credited_date_conversions'],434)
        self.assertEqual(r['audit']['scalar_checks_replayed'],114)

    def test_all_float_delivery_routes_are_explicit(self):
        mapping=json.loads((ROOT/'paper/result-map.json').read_text())
        self.assertEqual(len(mapping['entries']),25)
        for row in mapping['entries']:
            self.assertEqual(row['delivery_scope'],'docs/release-scope.md')
            for name in row['public_evidence']:self.assertTrue((ROOT/name).is_file())
        entries={r['label']:r for r in mapping['entries']}
        self.assertIn('anonymous cell-outcome recount',entries['tab:rayyan']['evidence_scope'])
        self.assertIn('raw TabClean scoring only with external originals',entries['tab:rayyan']['evidence_scope'])
        self.assertIn('saved-summary projections',entries['tab:p1']['evidence_scope'])
        self.assertIn('A04',entries['tab:beers']['evidence_scope'])
        self.assertIn('A04',entries['tab:decoding']['evidence_scope'])


if __name__=='__main__':unittest.main()
