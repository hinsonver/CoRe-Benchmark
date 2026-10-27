from .core_runtime import evidence_json, evidence_glob, evidence_paths, movie_view, read_witnesses, public_mode
'Model-scale gradient: the same P2 and near-entity results for every model, side by side.\n\nFor each model: repair F1 on the four conditions (identity columns) and the paired differences\n(memory, entity knowledge, spelling knowledge) per dataset; near-entity rewrite rates over the\nentities that model itself knows; and, for the Beers negative control, how many "City ST" errors\nit repairs per condition with a sign test over chunks (at near-zero scores the bootstrap star is\nunreliable: Qwen-32B\'s "significant" words-vs-syllable gap is 1 vs 11 repaired cells in 7 chunks).\n\nUsage: .venv/bin/python -m src.scale   (writes results/scale_summary.json, prints the tables)\n'
import collections
import json
import os
from math import comb
from .data import ARCHIVE, BUILD, ROOT, load
from .screening import known_key_rates
from .probe_clean import OUT, bootstrap_diff, f1_of, norm, parse
MODELS = [('local_olmo2-7b', 'OLMo-2-7B', 7), ('local_qwen2.5-7b', 'Qwen2.5-7B', 7), ('local_llama3.1-8b', 'Llama-3.1-8B', 8), ('local_qwen2.5-14b', 'Qwen2.5-14B', 14), ('local_qwen2.5-32b-awq', 'Qwen2.5-32B', 32), ('custom_deepseek_deepseek-v4-pro', 'DeepSeek-V4-Pro', None), ('custom_qwen_qwen3.8-max', 'Qwen3.8-Max', None), ('custom_z-ai_glm-5.3', 'GLM-5.3', None), ('openai_gpt-6.1-sol', 'GPT-6.1-Sol', None)]
CONDS = {'hospital': ['hospital', 'hospital_fresh', 'hospital_surrogatewords', 'hospital_surrogate'], 'movies': ['movies', 'movies_fresh', 'movies_surrogatewords', 'movies_surrogate'], 'beers': ['beers_orig', 'beers_fresh', 'beers_surrogatewords', 'beers_surrogate']}
NAMES = ['original', 'fresh', 'words', 'syllable']

def chunks(tag: str, cond: str) -> list[dict]:
    return evidence_json(OUT / f'{tag}__{cond}__k20__spread.json')['chunks']

def p2(tag: str, base: str, group: str='identity') -> dict:
    o, f, w, s = (chunks(tag, c) for c in CONDS[base])
    res = {'f1': {n: round(f1_of(c, group), 3) for n, c in zip(NAMES, (o, f, w, s))}, 'predicted': {n: sum((ch['counts'][group]['predicted'] for ch in c)) for n, c in zip(NAMES, (o, f, w, s))}}
    for name, a, b, paired in (('memory', o, f, False), ('entity', f, w, False), ('spelling', w, s, True), ('entity_paired', o, w, True)):
        d, lo, hi = bootstrap_diff(a, b, group, paired)
        res[name] = {'diff': round(d, 3), 'ci': [round(lo, 3), round(hi, 3)]}
    return res

def sign_test(up: int, down: int) -> float:
    n = up + down
    return 1.0 if not n else min(1.0, 2 * sum((comb(n, i) for i in range(min(up, down) + 1))) / 2 ** n)

def beers_city(tag: str) -> dict:
    """Beers identity errors are all "City ST" in the city column. Per condition: cells repaired,
    chunks with a repair, correct cities edited; then words vs syllable surrogate by chunk."""
    res, per = ({}, {})
    for name, cond in zip(NAMES, CONDS['beers']):
        dirty, clean = load(cond)
        rep, bad = (collections.Counter(), 0)
        for ch in chunks(tag, cond):
            pred = {}
            for p in parse(ch['output']):
                try:
                    r = ch['rows'][int(p['row']) - 1]
                except (TypeError, ValueError, IndexError):
                    continue
                if str(p['column']) == 'city':
                    pred[r] = str(p['value']).strip()
            for r, v in pred.items():
                d, g = (dirty.at[r, 'city'], clean.at[r, 'city'])
                if norm(v) == norm(d):
                    continue
                if d != g and norm(v) == norm(g):
                    rep[ch['start']] += 1
                elif d == g:
                    bad += 1
        per[name] = rep
        res[name] = {'repaired': sum(rep.values()), 'chunks_with_repair': len(rep), 'correct_cities_edited': bad}
    w, s = (per['words'], per['syllable'])
    up = sum((1 for k in set(w) | set(s) if s[k] > w[k]))
    down = sum((1 for k in set(w) | set(s) if s[k] < w[k]))
    res['words_vs_syllable'] = {'chunks_syllable_more': up, 'chunks_words_more': down, 'sign_test_p': round(sign_test(up, down), 3)}
    return res

def near(tag: str) -> dict:
    res = {}
    for ds in ('hospital', 'beers', 'movies'):
        s = evidence_json(ARCHIVE / 'near' / f'{tag}__{ds}__summary.json')
        rates = known_key_rates(ROOT / 'data/final/_near', ds, tag, s)
        res[ds] = {'known': s['screened_known']['known'], 'targets': s['screened_known']['targets'], **{k: v for k, v in rates.items() if not k.startswith('control')}}
    return res

def main() -> None:
    out = {}
    for tag, name, size in MODELS:
        out[name] = {'params_b': size, 'p2': {b: p2(tag, b) for b in CONDS}, 'beers_city': beers_city(tag), 'near': near(tag)}
    target = BUILD / 'derived' / 'scale_summary.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    if os.environ.get('CORE_COLLECT_ONLY'):
        print('Collected conditional scores and counts for cluster inference.')
        return
    star = lambda e: '*' if e['ci'][0] > 0 or e['ci'][1] < 0 else ' '
    for base in CONDS:
        print(f'\n{base}, identity columns: repair F1 and differences (95% bootstrap CI over chunks)')
        print(f"{'model':16s} {'orig':>5s} {'fresh':>5s} {'words':>5s} {'syll':>5s}   {'memory':>8s} {'entity':>8s} {'spelling':>8s} {'ent.pair':>8s}")
        for name, m in out.items():
            r = m['p2'][base]
            print(f'{name:16s} ' + ' '.join((f"{r['f1'][n]:5.2f}" for n in NAMES)) + '   ' + ' '.join((f"{r[k]['diff']:+7.2f}{star(r[k])}" for k in ('memory', 'entity', 'spelling', 'entity_paired'))))
    print('\nBeers city errors repaired (of 127) / correct cities edited; words vs syllable by chunk')
    for name, m in out.items():
        b = m['beers_city']
        print(f'{name:16s} ' + '  '.join((f"{b[n]['repaired']:3d}/{b[n]['correct_cities_edited']:<3d}" for n in NAMES)) + f"   syllable more {b['words_vs_syllable']['chunks_syllable_more']}, words more {b['words_vs_syllable']['chunks_words_more']}, p = {b['words_vs_syllable']['sign_test_p']:.3f}")
    print('\nNear-entity: famous entity with another fact, rewritten to the real fact (entities the model knows)')
    print(f"{'model':16s} {'movies known':>12s} {'standard':>9s} {'evidence':>9s}   {'hospital std':>12s} {'beers std':>9s}")
    for name, m in out.items():
        n = m['near']
        print(f"{name:16s} {n['movies']['known']:>9d}/{n['movies']['targets']:<2d} {n['movies']['real|1|standard']['rate']:9.2f} {n['movies']['real|1|evidence']['rate']:9.2f}   {n['hospital']['real|1|standard']['rate']:12.2f} {n['beers']['real|1|standard']['rate']:9.2f}")
if __name__ == '__main__':
    main()
