from .core_runtime import evidence_json, evidence_glob, evidence_paths, movie_view, read_witnesses, public_mode
'Aligned comparison of Baran and an LLM: same view, same labels, same task.\n\nE5 gave Baran the whole table (it can copy a hospital\'s name from its 24 other rows) and 20\nlabeled tuples, while the LLM saw 20-row chunks of distinct entities, zero-shot. Here both get:\n  view    the P2 chunks (--spread): 20 rows of 20 different entities\n  labels  the same 20 labeled tuples (dirty row -> clean row), the ones Baran itself samples on\n          the whole table (seed 0); the original\'s are reused for its surrogates (same rows and\n          error cells), so those runs stay paired chunk by chunk\n  task    repair only: both are told which cells are wrong (Baran\'s own "perfect detection")\nLabeled rows are left out of scoring. What remains different is the method, and the knowledge\nthe LLM can draw on.\n\nSteps (Baran needs the raha venv, the LLM the main one):\n  .venv-e5/bin/python -m src.aligned labels --base hospital\n  .venv-e5/bin/python -m src.aligned baran  --base hospital\n  .venv/bin/python    -m src.aligned llm    --base hospital --model custom:deepseek/deepseek-v4-pro\n  .venv/bin/python    -m src.aligned compare --base hospital --model custom:deepseek/deepseek-v4-pro\nResults: results/aligned/\n'
import argparse
import json
import os
from pathlib import Path
import random
import shutil
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from .data import ARCHIVE, BUILD, load, to_csv_block
from .probe_clean import ENTITY, IDENTITY, ORIGINAL, SYSTEM, base_name, norm, parse, spread_chunks
OUT = Path(os.environ.get('CORE_ALIGNED_DIR', ARCHIVE / 'aligned')).resolve()
WORK = BUILD / 'work' / 'aligned'
K = 20

def conditions(base: str) -> list[str]:
    return [ORIGINAL.get(base, base), f'{base}_fresh', f'{base}_surrogatewords', f'{base}_surrogate']

def label_source(cond: str, base: str) -> str:
    """Surrogates share the original's rows and error cells, so they reuse its labels."""
    return cond if cond.endswith('_fresh') else ORIGINAL.get(base, base)

def chunks_of(cond: str) -> list[list[int]]:
    _, clean = load(cond)
    return spread_chunks(clean, ENTITY[base_name(cond)], K)

def _raha():
    import raha
    import raha.correction
    from .e5_baselines import InProcessPool
    raha.correction.Pool = InProcessPool
    return raha

def _dataset(raha, name: str, dirty, clean):
    work = WORK / name
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    dirty.to_csv(work / 'dirty.csv', index=False)
    clean.to_csv(work / 'clean.csv', index=False)
    d = raha.dataset.Dataset({'name': name, 'path': str(work / 'dirty.csv'), 'clean_path': str(work / 'clean.csv')})
    d.detected_cells = dict(d.get_actual_errors_dictionary())
    return (d, work)

def corrector(raha):
    c = raha.correction.Correction()
    c.PRETRAINED_VALUE_BASED_MODELS_PATH = ''
    c.VERBOSE = False
    c.SAVE_RESULTS = False
    c.NUM_WORKERS = 1
    return c

def choose_labels(base: str, seed: int=0, only: list[str] | None=None) -> dict:
    """The 20 tuples Baran samples on the whole table (perfect detection). With `only`, just
    those conditions' labels are redrawn and the others kept."""
    raha = _raha()
    path = OUT / f'labels_{base}.json'
    out = evidence_json(path) if only and path.exists() else {}
    for cond in {label_source(c, base) for c in conditions(base) if not only or c in only}:
        dirty, clean = load(cond)
        random.seed(seed)
        np.random.seed(seed)
        d, work = _dataset(raha, f'labels_{cond}', dirty, clean)
        corrector(raha).run(d)
        out[cond] = [int(i) for i in d.labeled_tuples]
        shutil.rmtree(work, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    return out

def baran_chunks(base: str, run: int | None=None, max_chunks: int | None=None, only: list[str] | None=None) -> None:
    """Baran on each chunk: the chunk's rows plus the 20 labeled tuples, nothing else.

    With `run`, every chunk is seeded (run, chunk) and the result goes to baran__<cond>__run<r>.json:
    unseeded, two runs on the same data differed by about 0.05 F1 (Baran samples internally)."""
    raha = _raha()
    labels = evidence_json(OUT / f'labels_{base}.json')
    for cond in [c for c in conditions(base) if not only or c in only]:
        dirty, clean = load(cond)
        L = labels[label_source(cond, base)]
        results = []
        for ci, rows in enumerate(chunks_of(cond)[:max_chunks]):
            if run is not None:
                random.seed(run * 100003 + ci)
                np.random.seed(run * 100003 + ci)
            keep = [i for i in rows if i not in L]
            view = L + keep
            d, work = _dataset(raha, f'{cond}_{ci}', dirty.iloc[view].reset_index(drop=True), clean.iloc[view].reset_index(drop=True))
            c = corrector(raha)
            c.initialize_dataset(d)
            c.initialize_models(d)
            for local in range(len(L)):
                d.sampled_tuple = local
                c.label_with_ground_truth(d)
                c.update_models(d)
            c.predict_corrections(d)
            cols = list(clean.columns)
            fixes = {(view[i], cols[j]): v for (i, j), v in d.corrected_cells.items() if i >= len(L)}
            results.append({'chunk': ci, 'rows': keep, 'fixes': [[i, c_, v] for (i, c_), v in fixes.items()]})
            shutil.rmtree(work, ignore_errors=True)
        name = f'baran__{cond}.json' if run is None else f'baran__{cond}__run{run}.json'
        (OUT / name).write_text(json.dumps(results, ensure_ascii=False))
        print(cond, 'done', flush=True)
PROMPT = 'The CSV table below contains erroneous cells. Their positions are listed after the table, as (_row, column). Give the correct value of each listed cell.\n\nTo show this table\'s conventions, here are {n} other rows of the same table with errors, each as its erroneous version followed by its corrected version:\n\n{examples}\n\nTable:\n{block}\n\nErroneous cells:\n{cells}\n\nReply with JSON: {{"corrections": [{{"row": <_row>, "column": "<column name>", "value": "<corrected value>"}}]}}\n'

def llm(base: str, model: str, workers: int=8, max_tokens: int=4096, only: list[str] | None=None) -> None:
    from .clients import complete_json
    labels = evidence_json(OUT / f'labels_{base}.json')
    tag = model.replace(':', '_').replace('/', '_')
    for cond in [c for c in conditions(base) if not only or c in only]:
        dirty, clean = load(cond)
        cols = list(clean.columns)
        L = labels[label_source(cond, base)]
        examples = '\n\n'.join((f'Erroneous:\n{to_csv_block(dirty.iloc[[i]])}\nCorrected:\n{to_csv_block(clean.iloc[[i]])}' for i in L))
        jobs = []
        for rows in chunks_of(cond):
            keep = [i for i in rows if i not in L]
            shown = dirty.iloc[keep].reset_index(drop=True)
            shown.insert(0, '_row', range(1, len(keep) + 1))
            cells = [(r + 1, c) for r, i in enumerate(keep) for c in cols if dirty.at[i, c] != clean.at[i, c]]
            jobs.append((keep, PROMPT.format(n=len(L), examples=examples, block=to_csv_block(shown), cells='\n'.join((f'({r}, {c})' for r, c in cells)))))
        with ThreadPoolExecutor(workers) as ex:
            outs = list(ex.map(lambda j: complete_json(model, j[1], system=SYSTEM, max_tokens=max_tokens), jobs))
        results = []
        for ci, ((keep, _), out) in enumerate(zip(jobs, outs)):
            fixes = []
            for p in parse(out):
                try:
                    r = int(p['row']) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= r < len(keep) and p['column'] in cols:
                    fixes.append([keep[r], p['column'], str(p['value']).strip()])
            results.append({'chunk': ci, 'rows': keep, 'fixes': fixes, 'output': out})
        (OUT / f'{tag}__{cond}.json').write_text(json.dumps(results, ensure_ascii=False))
        print(cond, 'done', flush=True)

def score(cond: str, results: list[dict]) -> list[dict]:
    """Per chunk counts over the error cells of its scored rows (repair only: only listed cells count)."""
    if isinstance(results, dict) and results.get('__core_witness__') == 'aligned_counts_v1':
        return results['chunks']
    dirty, clean = load(cond)
    ident = set(IDENTITY[base_name(cond)])
    out = []
    for r in results:
        fixes = {(i, c): v for i, c, v in r['fixes']}
        counts = {g: {'errors': 0, 'predicted': 0, 'repaired': 0, 'detected': 0} for g in ('all', 'identity', 'other')}
        for i in r['rows']:
            for c in clean.columns:
                if dirty.at[i, c] == clean.at[i, c]:
                    continue
                v = fixes.get((i, c))
                changed = v is not None and norm(v) != norm(dirty.at[i, c])
                for g in ('all', 'identity' if c in ident else 'other'):
                    counts[g]['errors'] += 1
                    counts[g]['predicted'] += changed
                    counts[g]['detected'] += changed
                    counts[g]['repaired'] += changed and norm(v) == norm(clean.at[i, c])
        out.append({'counts': counts})
    return out

def compare(base: str, model: str) -> dict:
    from .probe_clean import bootstrap_diff, f1_of
    tag = model.replace(':', '_').replace('/', '_')
    table, runs = ({}, {})
    for cond in conditions(base):
        p = OUT / f'{tag}__{cond}.json'
        if p.exists():
            table['llm', cond] = score(cond, evidence_json(p))
        files = sorted(evidence_paths(OUT, f'baran__{cond}__run*.json')) or [OUT / f'baran__{cond}.json']
        runs[cond] = [score(cond, evidence_json(f)) for f in files if f.exists()]
    summary = {}
    print(f"{'condition':24s} {'group':9s} {'Baran F1 (runs)':>22s} {'LLM F1':>8s}  LLM - Baran [95% CI, first run]")
    for cond in conditions(base):
        for g in ('all', 'identity', 'other'):
            bs, l = (runs.get(cond), table.get(('llm', cond)))
            if not (bs and l):
                continue
            f1s = [f1_of(b, g) for b in bs]
            d, lo, hi = bootstrap_diff(l, bs[0], g, paired=True)
            mean = sum(f1s) / len(f1s)
            summary[f'{cond}|{g}'] = {'baran': round(mean, 3), 'baran_runs': [round(x, 3) for x in f1s], 'llm': round(f1_of(l, g), 3), 'llm_minus_baran': [round(f1_of(l, g) - mean, 3), round(lo, 3), round(hi, 3)]}
            print(f"{cond:24s} {g:9s} {mean:7.3f} ({'/'.join((f'{x:.2f}' for x in f1s))}) {f1_of(l, g):8.3f}  {f1_of(l, g) - mean:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    (OUT / f'compare__{base}__{tag}.json').write_text(json.dumps(summary, indent=1))
    return summary

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['labels', 'baran', 'llm', 'compare'])
    ap.add_argument('--base', nargs='+', default=['hospital', 'movies', 'beers'])
    ap.add_argument('--model', default='custom:deepseek/deepseek-v4-pro')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--runs', nargs='*', type=int, default=[], help='baran: seeded runs (files baran__<cond>__run<r>.json)')
    ap.add_argument('--max-chunks', type=int, default=None, help='baran: only the first chunks (for checks)')
    ap.add_argument('--only', nargs='*', default=None, help='labels/baran/llm: only these conditions, e.g. movies_fresh')
    a = ap.parse_args()
    for base in a.base:
        if a.step == 'labels':
            print(base, choose_labels(base, only=a.only))
        elif a.step == 'baran':
            for r in a.runs or [None]:
                baran_chunks(base, r, a.max_chunks, a.only)
        elif a.step == 'llm':
            llm(base, a.model, a.workers, only=a.only)
        else:
            compare(base, a.model)
if __name__ == '__main__':
    main()
