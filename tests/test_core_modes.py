"""Offline controls for the statistical-core distribution."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from src import core_runtime as runtime


class CoreModes(unittest.TestCase):
    def test_movie_records_absent(self):
        sources=json.loads((ROOT/'data/manifests/CORE_SOURCES.json').read_text())
        self.assertEqual(len(sources['omitted_files']),254)
        self.assertTrue(all(not (ROOT/p).exists() for p in sources['omitted_files']))

    def test_witness_schema(self):
        witness=runtime.read_witnesses(ROOT)
        self.assertEqual(len(witness['near']),9)
        self.assertEqual(len(witness['archives']),180)
        runtime.check_payload(witness)

    def test_public_data_loading_fails(self):
        with self.assertRaisesRegex(ValueError,'excluded'):
            runtime.private_file('data/final/movies/clean.csv',ROOT)

    def test_missing_authorization_fails(self):
        with self.assertRaisesRegex(ValueError,'authorization'):
            runtime.preflight_private(ROOT,ROOT.parent/'private',None)

    def test_missing_known_subset_fails(self):
        with self.assertRaises((ValueError,FileNotFoundError)):
            runtime.movie_known_key_rates('missing-model',{},ROOT)


if __name__=='__main__':unittest.main()
