"""Numerical and fail-closed tests for the conditional cluster-inference entry."""
from pathlib import Path
import hashlib,json,sys,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
from src import cluster_statistics as c

class ClusterStatistics(unittest.TestCase):
    def test_micro_f1(self):
        self.assertAlmostEqual(c.weighted_f1([[1,1,1],[9,1,0]],np.ones((1,2)))[0],1/6)
    def test_zero_denominator(self):
        self.assertEqual(c.weighted_f1(np.zeros((2,3)),np.ones((1,2)))[0],0.)
    def test_negative_weights(self):
        with self.assertRaises(ValueError):c.weighted_f1([[1,1,1]],[[-1]])
    def test_entity_weight_not_reply_mean(self):
        np.testing.assert_allclose(c.cluster_rates([1,0],[1,3],[[1,1],[2,1]]),[.25,.4])
    def test_boundary_rate_no_interval(self):
        r=c.rate_interval([{'entity':0,'reply':0,'hits':[0]},{'entity':1,'reply':0,'hits':[0]}],100,17)
        self.assertFalse(r['interval_available']);self.assertEqual(r['rate'],0)
    def test_support3(self):
        r=c.rate_interval([{'entity':0,'reply':0,'hits':[1,0,0]},{'entity':1,'reply':1,'hits':[0,0,0]}],100,17)
        self.assertEqual(r['entities'],2);self.assertAlmostEqual(r['rate_exact'],1/6)
    def test_centered_positive_tail(self):
        self.assertGreater(c.centered_p(np.array([.001,.005,.01,.02,.1]),.01),.05)
    def test_holm(self):self.assertEqual(c.holm([.01,.04,.03]),[.03,.06,.06])
    def test_zero_difference(self):self.assertEqual(c.centered_p(np.zeros(50),0),1.)
    def test_labels(self):self.assertEqual(c.condition_code('Words surrogate'),'W')
    def test_fixed_scope(self):
        d=json.loads((ROOT/'results/derived/cluster_statistics.json').read_text())
        self.assertEqual(len(d['main_family']),40);self.assertEqual(len(d['beers_family']),8)
        self.assertEqual(sum(d['contrasts'][k]['significant'] for k in d['main_family']),27)
        self.assertEqual(d['replicates'],50000)
    def test_witness_provenance(self):
        d=c.read_witness(ROOT)
        self.assertEqual(d['verification']['near_settings'],240)
        self.assertEqual(d['verification']['historical_input_runs'],3)
        self.assertEqual(d['verification']['integer_count_checks'],57600)
    def test_two_stage_table_hashes(self):
        config=json.loads((ROOT/'code/config/paper_presentation.json').read_text())
        for name in ('decomposition.tex','counts.tex','beers.tex','near.tex'):
            spec=config['sources'][name]
            self.assertNotEqual(spec['input_body_sha256'],spec['body_sha256'])
    def test_current_source_statistics(self):
        d=json.loads((ROOT/'results/derived/cluster_statistics.json').read_text());p=ROOT/'data/witnesses/cluster_statistics.json'
        self.assertEqual(d['witness_sha256'],hashlib.sha256(p.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main()
