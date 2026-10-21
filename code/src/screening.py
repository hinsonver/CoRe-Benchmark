from .core_runtime import evidence_json, evidence_glob, evidence_paths, movie_view, read_witnesses, public_mode
'Fail-closed screening dependency policy for the public CoRe candidate (standard library).'
import csv
import hashlib
import json
from pathlib import Path
GPT = 'openai_gpt-6.1-sol'

def known_names(near, ds, model):
    near = Path(near)
    tag = model.replace(':', '_').replace('/', '_')
    path = near / f'screen_plan_{ds}__{tag}.csv'
    if not path.is_file():
        raise FileNotFoundError(f'Required screening file missing: {path.name}; refusing all-target fallback')
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        if not {'name', 'known'} <= set(reader.fieldnames or []):
            raise ValueError(f'Invalid screening columns: {path.name}')
        rows = list(reader)
    if not rows or any((r['known'] not in {'True', 'False'} or not r['name'] for r in rows)):
        raise ValueError(f'Invalid screening flags/names: {path.name}')
    names = [r['name'] for r in rows]
    if len(set(names)) != len(names):
        raise ValueError(f'Duplicate screening names: {path.name}')
    if tag == GPT:
        manifest = near.parent.parent / 'manifests/GPT_SCREENING.json'
        if not manifest.is_file():
            raise FileNotFoundError('Required GPT screening hash manifest missing')
        expected = evidence_json(manifest)['files'][ds]
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256']:
            raise ValueError(f'Screening hash mismatch: {path.name}')
    plan = evidence_json(near / ds / 'plan.json')
    if set(names) != {p['famous']['name'] for p in plan['plan']} or len(rows) != plan['targets']:
        raise ValueError(f'Screening pool differs from fixed plan: {path.name}')
    known = {r['name'] for r in rows if r['known'] == 'True'}
    if not known:
        raise ValueError(f'Known subset is empty: {path.name}')
    return known

def known_key_rates(near, ds, model, summary):
    if ds == 'movies' and public_mode():
        from .core_runtime import movie_known_key_rates
        return movie_known_key_rates(model, summary)
    known = known_names(near, ds, model)
    targets = evidence_json(Path(near) / ds / 'plan.json')['targets']
    if summary.get('screened_known') != {'known': len(known), 'targets': targets}:
        raise ValueError(f'Known screening denominator mismatch: {ds}, {model}')
    rates = summary.get('key_rates_known')
    if not isinstance(rates, dict) or not rates:
        raise ValueError(f'Required known-subset rates missing: {ds}, {model}; refusing all-target fallback')
    plan = evidence_json(Path(near) / ds / 'plan.json')
    expected = {f'{t}|{s}|{p}' for t in ('real', 'near', 'control') for s in plan['chunk_rows'] for p in ('standard', 'evidence')}
    if set(rates) != expected or any((r.get('entities') != len(known) for r in rates.values())):
        raise ValueError(f'Known rate settings/denominator mismatch: {ds}, {model}')
    return rates

def check_all(root):
    root = Path(root)
    raw, near = (root / 'artifacts/raw_outputs/near', root / 'data/final/_near')
    files = sorted(evidence_paths(raw, '*__summary.json'))
    if len(files) != 27:
        raise ValueError('Expected 27 archived screening/summary pairs (eight main models plus archived OLMo)')
    gpt = {}
    for path in files:
        model, ds, _ = path.stem.split('__')
        summary = evidence_json(path)
        rates = known_key_rates(near, ds, model, summary)
        if model == GPT:
            gpt[ds] = {**summary['screened_known'], 'settings': len(rates)}
    return {'screening_files': len(files), 'gpt': gpt, 'fallback': 'forbidden'}
