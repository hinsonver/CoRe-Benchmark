from .core_runtime import evidence_json, evidence_glob, evidence_paths, movie_view, read_witnesses, public_mode
"Construction-seed variation: P2 on the fresh and surrogate tables built with seeds 0, 1, 2.\n\nA seed redraws what is random in a table's construction (validate_tables checks the tables):\nthe fresh table's errors; a surrogate's fictitious values and, for Hospital, its error\ncharacters. The original table has no seed. Per model and dataset this prints the identity-\ncolumn repair F1 of each seed and the knowledge effects computed seed by seed, so the spread\nacross seeds can be set against the bootstrap interval over chunks of a single seed.\n\nUsage: .venv/bin/python -m src.seeds   (writes results/seed_summary.json)\n"
import json
import statistics
from .clients import truncated
from .data import BUILD, load
from .probe_clean import OUT, f1_of
SEEDS = [0, 1, 2]
MODELS = [('local_qwen2.5-7b', 'Qwen2.5-7B'), ('local_llama3.1-8b', 'Llama-3.1-8B'), ('local_qwen2.5-14b', 'Qwen2.5-14B'), ('local_qwen2.5-32b-awq', 'Qwen2.5-32B'), ('custom_deepseek_deepseek-v4-pro', 'DeepSeek-V4-Pro'), ('custom_qwen_qwen3.8-max', 'Qwen3.8-Max'), ('custom_z-ai_glm-5.3', 'GLM-5.3'), ('openai_gpt-6.1-sol', 'GPT-6.1-Sol')]
KINDS = ['fresh', 'surrogatewords', 'surrogate']

def chunks(tag: str, table: str) -> list[dict]:
    r = evidence_json(OUT / f'{tag}__{table}__k20__spread.json')
    if table.startswith('movies'):
        if sum((ch['counts']['all']['errors'] for ch in r['chunks'])) != r['summary']['all']['errors']:
            raise ValueError('Movie numeric error denominator mismatch')
    else:
        d, c = load(table)
        if r['summary']['all']['errors'] != int((d.values != c.values).sum()):
            raise RuntimeError(f'{tag} {table}: result was not computed on the current table')
    return r['chunks']

def main() -> None:
    out = {}
    for base in ('hospital', 'movies'):
        print(f'\n{base}, identity columns, repair F1 by construction seed (0 / 1 / 2) and mean')
        print(f"{'model':14s} {'orig':>5s}  {'fresh':^23s} {'words':^23s} {'syllable':^23s}  {'entity (fresh-words)':^26s} {'spelling (words-syll)':^26s} {'total (orig-syll)':^26s} trunc")
        for tag, name in MODELS:
            o = f1_of(chunks(tag, base), 'identity')
            f1, trunc = ({}, 0)
            for k in KINDS:
                f1[k] = []
                for s in SEEDS:
                    ch = chunks(tag, f'{base}_{k}' + ('' if s == 0 else f'_s{s}'))
                    f1[k].append(f1_of(ch, 'identity'))
                    trunc += sum((x['truncated'] if 'truncated' in x else truncated(x['output']) for x in ch))
            eff = {'entity': [a - b for a, b in zip(f1['fresh'], f1['surrogatewords'])], 'spelling': [a - b for a, b in zip(f1['surrogatewords'], f1['surrogate'])], 'total': [o - b for b in f1['surrogate']]}
            cell = lambda v, sign='': '/'.join((f'{x:{sign}.2f}' for x in v)) + f' ({statistics.mean(v):{sign}.2f})'
            print(f'{name:14s} {o:5.2f}  ' + ' '.join((f'{cell(f1[k]):^23s}' for k in KINDS)) + '  ' + ' '.join((f"{cell(eff[k], '+'):^26s}" for k in ('entity', 'spelling', 'total'))) + f' {trunc}')
            out[f'{name}|{base}'] = {'original': round(o, 3), **{k: [round(x, 3) for x in v] for k, v in f1.items()}, **{k: {'by_seed': [round(x, 3) for x in v], 'mean': round(statistics.mean(v), 3), 'range': round(max(v) - min(v), 3)} for k, v in eff.items()}, 'truncated_replies': trunc}
    target = BUILD / 'derived' / 'seed_summary.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1))
if __name__ == '__main__':
    main()
