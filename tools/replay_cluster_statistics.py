"""Recompute conditional cluster statistics offline from hash-bound anonymous witnesses."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
from src.cluster_statistics import run

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'build/cluster-statistics.json')
    a=p.parse_args()
    if a.output.exists():raise SystemExit('Choose a new output path; refusing overwrite')
    r=run(ROOT,a.output)
    print(json.dumps({'main_family':len(r['main_family']),'beers_family':len(r['beers_family']),
        'known_settings':sum(len(x) for v in r['near'].values() for x in v.values()),'new_model_calls':0}))
