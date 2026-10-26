from .core_runtime import evidence_json, evidence_glob, evidence_paths, movie_view, read_witnesses, public_mode
import os
from .screening import known_key_rates
"LaTeX tables for the paper, computed from the result files (no number is typed by hand).\n\nWrites one file per table to ../论文/latex/tables/<name>.tex (never main.tex: Overleaf would take it for the root document) (a complete table environment with\ncaption and label), to be \\input in main.tex. Rerun after any new result:\n  .venv/bin/python -m src.paper_tables\nDifferences are bootstrapped as in the analyses (src.probe_clean.bootstrap_diff): 2,000 resamples\nover chunks, paired where the two conditions share rows (O, W, S). Each table's differences form one\nfamily: a two-sided bootstrap p-value per difference, Holm-corrected over the family, and a\ndifference is marked ($^\\dagger$) when its corrected p is below 0.05. Near-zero Beers comparisons\nuse counts and a sign test over chunks.\n"
import collections
import glob
import json
import math
import random
from pathlib import Path
from .data import ARCHIVE, BUILD, ROOT, load
from .probe_clean import OUT, bootstrap_diff, f1_of
TEX = Path(os.environ.get('CORE_TABLE_DIR', BUILD / 'tables')).resolve()
COMMERCIAL = [('custom_deepseek_deepseek-v4-pro', 'DeepSeek-V4-Pro'), ('custom_qwen_qwen3.8-max', 'Qwen3.8-Max'), ('custom_z-ai_glm-5.3', 'GLM-5.3'), ('openai_gpt-6.1-sol', 'GPT-6.1-Sol')]
OPEN = [('local_qwen2.5-7b', 'Qwen2.5-7B'), ('local_llama3.1-8b', 'Llama-3.1-8B'), ('local_qwen2.5-14b', 'Qwen2.5-14B'), ('local_qwen2.5-32b-awq', 'Qwen2.5-32B')]
CONDS = {'hospital': ['hospital', 'hospital_fresh', 'hospital_surrogatewords', 'hospital_surrogate'], 'movies': ['movies', 'movies_fresh', 'movies_surrogatewords', 'movies_surrogate'], 'beers': ['beers_orig', 'beers_fresh', 'beers_surrogatewords', 'beers_surrogate']}
G = 'identity'
SHORT = {'DeepSeek-V4-Pro': 'DeepSeek', 'Qwen3.8-Max': 'Qwen3.8', 'GLM-5.3': 'GLM-5.3', 'GPT-6.1-Sol': 'GPT-6.1', 'Qwen2.5-7B': 'Qwen-7B', 'Llama-3.1-8B': 'Llama-8B', 'Qwen2.5-14B': 'Qwen-14B', 'Qwen2.5-32B': 'Qwen-32B'}

def dot2(v):
    """Two decimals without the leading zero (".95"), "1.0" for values that round to 1."""
    t = f'{v:.2f}'
    return '1.0' if t == '1.00' else t[1:] if t.startswith('0') else t
pv = lambda q: '$<$.001' if q < 0.001 else f'{q:.3f}'[1:] if q < 1 else '1'

def chunks(tag, cond):
    return evidence_json(OUT / f'{tag}__{cond}__k20__spread.json')['chunks']

def seeded(cond, s):
    return cond if s == 0 or cond in ('hospital', 'movies', 'beers_orig') else f'{cond}_s{s}'

def f2(x):
    return f'{x:.2f}'

def sgn(x):
    """Signed difference with two decimals; -0.00 prints as +0.00 and the minus sign is typeset."""
    t = f'{x:+.2f}'
    return '+0.00' if t == '-0.00' else t.replace('-', '$-$')

class Family:
    """Differences of one table: bootstrap p-values, Holm-corrected when the table is rendered."""

    def __init__(self):
        self.items = []

    def add(self, a, b, paired, n=2000, seed=0):
        rng = random.Random(seed)
        ds = []
        for _ in range(n):
            if paired:
                idx = [rng.randrange(len(a)) for _ in a]
                sa, sb = ([a[i] for i in idx], [b[i] for i in idx])
            else:
                sa = [a[rng.randrange(len(a))] for _ in a]
                sb = [b[rng.randrange(len(b))] for _ in b]
            ds.append(f1_of(sa, G) - f1_of(sb, G))
        d = f1_of(a, G) - f1_of(b, G)
        p = min(1.0, 2 * min(sum((x <= 0 for x in ds)), sum((x >= 0 for x in ds))) / n) if d != 0 else 1.0
        key = f'@@{len(self.items)}@@'
        self.items.append((key, d, p))
        return key

    def render(self, text):
        """Replace each placeholder by the difference, marked when its Holm-corrected p < 0.05."""
        m, adj = (len(self.items), holm([p for _, _, p in self.items]))
        for i, (key, d, _) in enumerate(self.items):
            mark = '$^\\dagger$' if adj[i] < 0.05 else ''
            text = text.replace(key, sgn(d) + mark)
        return (text, m)

def write(name, body):
    TEX.mkdir(parents=True, exist_ok=True)
    (TEX / f'{name}.tex').write_text(body)
    print('wrote', TEX / f'{name}.tex')

def main_table():
    fam = Family()
    rows = []
    for group in (COMMERCIAL, OPEN):
        for tag, name in group:
            h = [chunks(tag, c) for c in CONDS['hospital']]
            m = [chunks(tag, c) for c in CONDS['movies']]
            hf = [f2(f1_of(x, G)) for x in h]
            mf = [f2(f1_of(x, G)) for x in m]
            rows.append(' & '.join([name] + hf + [fam.add(h[1], h[2], False), fam.add(h[2], h[3], True), fam.add(h[0], h[3], True)] + mf + [fam.add(m[1], m[2], False), fam.add(m[0], m[2], True)]) + ' \\\\')
        rows.append('\\midrule')
    rows.pop()
    body, n_tests = fam.render('\n'.join(('    ' + r for r in rows)))
    write('decomposition', '\\begin{table*}[t]\n  \\caption{Knowledge contributes substantially to identity-column repair on Hospital and to Movies repair for the\n  commercial models. Repair F1 in the four conditions\n  (O original, F fresh, W words surrogate, S syllable\n  surrogate) and condition contrasts: fresh--words F$-$W, spelling W$-$S, total O$-$S, and paired entity familiarity\n  O$-$W (definitions and assumptions in Section~\\ref{sec:conditions}). $^\\dagger$: significant at 0.05 after Holm correction over the ' + str(n_tests) + ' differences of\n  this table (two-sided bootstrap over chunks, 2,000 resamples). Construction seed 0.}\n  \\label{tab:main}\n  \\small\n  \\begin{tabular*}{\\textwidth}{@{\\extracolsep{\\fill}}l cccc ccc cccc cc@{}}\n    \\toprule\n    & \\multicolumn{7}{c}{Hospital} & \\multicolumn{6}{c}{Movies} \\\\\n    \\cmidrule(lr){2-8}\\cmidrule(l){9-14}\n    Model & O & F & W & S & F$-$W & W$-$S & O$-$S & O & F & W & S & F$-$W & O$-$W \\\\\n    \\midrule\n' + body + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table*}\n')

def holm(ps):
    """Holm-adjusted p-values, in the order given."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    running, adj = (0.0, [0.0] * len(ps))
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj

def counts_table():
    """Identity errors repaired, as counts, with a sign test over paired chunks: W vs S on Hospital (spelling
    knowledge), O vs W on Movies (entity knowledge on the original rows). Holm-corrected over the models."""
    from .scale import sign_test
    tests = {'hospital': (2, 3), 'movies': (0, 2)}
    cells = {}
    for ds, (a, b) in tests.items():
        ps = []
        for tag, name in COMMERCIAL + OPEN:
            cs = [chunks(tag, c) for c in CONDS[ds]]
            assert [c['rows'] for c in cs[0]] == [c['rows'] for c in cs[2]] == [c['rows'] for c in cs[3]]
            r = [[c['counts'][G]['repaired'] for c in x] for x in cs]
            up = sum((x > y for x, y in zip(r[a], r[b])))
            dn = sum((x < y for x, y in zip(r[a], r[b])))
            ps.append(sign_test(up, dn))
            cells[ds, name] = [f'{sum(r[a])}/{sum(r[b])}', f'{up}:{dn}']
        for (tag, name), q in zip(COMMERCIAL + OPEN, holm(ps)):
            cells[ds, name].append(pv(q))
    errs = {ds: sum((c['counts'][G]['errors'] for c in chunks(COMMERCIAL[0][0], CONDS[ds][0]))) for ds in tests}
    rows = [' & '.join([SHORT[name]] + cells['hospital', name] + cells['movies', name]) + ' \\\\' for _, name in COMMERCIAL + OPEN]
    rows.insert(len(COMMERCIAL), '\\midrule')
    write('counts', '\\begin{table}[t]\n  \\caption{Near-zero scores as counts: the open models repair almost nothing on Movies. Identity errors repaired in the\n  two conditions compared (W/S of ' + str(errs['hospital']) + ' on Hospital, O/W of ' + str(errs['movies']) + ' on Movies); paired chunks in\n  which the first condition repairs more : fewer; sign-test $p$ values use separate eight-model Holm families by dataset.}\n  \\label{tab:counts}\n  \\small\n  \\setlength{\\tabcolsep}{3.5pt}\n  \\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}}l rrr rrr@{}}\n    \\toprule\n    & \\multicolumn{3}{c}{Hospital, W vs S} & \\multicolumn{3}{c}{Movies, O vs W} \\\\\n    \\cmidrule(lr){2-4}\\cmidrule(l){5-7}\n    Model & W/S & Chunks & $p$ & O/W & Chunks & $p$ \\\\\n    \\midrule\n' + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table}\n')

def example_table():
    """The same Hospital row in O, W and S (row 3), and a fresh row with an error in the same column."""
    from .data import load
    cols = [('HospitalName', 'Name'), ('Address1', 'Address'), ('City', 'City'), ('CountyName', 'County'), ('PhoneNumber', 'Phone')]
    tex = lambda v: str(v).replace('&', '\\&').replace('_', '\\_')
    rows = []
    for cond, label, i in (('hospital', 'O', 3), ('hospital_fresh', 'F$^*$', None), ('hospital_surrogatewords', 'W', 3), ('hospital_surrogate', 'S', 3)):
        d, c = load(cond)
        if i is None:
            i = next((k for k in range(len(d)) if d.at[k, 'City'] != c.at[k, 'City']))
        cells = [('\\textbf{%s}' if d.at[i, k] != c.at[i, k] else '%s') % tex(d.at[i, k]) for k, _ in cols]
        rows.append(' & '.join([label] + cells) + ' \\\\')
    write('example', '\\begin{table*}[t]\n  \\caption{One Hospital row in the four conditions (O original, F fresh, W words surrogate, S syllable surrogate), as the\n  model sees it (identity columns; the corrupted cell in bold).\n  O, W and S share the row and its error cell; only the names differ. $^*$The fresh table holds records of a newer\n  release of the registry, here a hospital of the benchmark under its current name with a measure the benchmark does\n  not have; it has as many error cells per column as the original.}\n  \\label{tab:example}\n  \\small\n  \\begin{tabular*}{\\textwidth}{@{\\extracolsep{\\fill}}lllllr@{}}\n    \\toprule\n    & ' + ' & '.join((n for _, n in cols)) + ' \\\\\n    \\midrule\n' + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table*}\n')

def movies_columns_table():
    """Errors repaired per column of Movies by DeepSeek-V4-Pro in O / F / W / S (repaired / errors)."""
    from .data import load
    from .probe_clean import norm, parse
    tag = 'custom_deepseek_deepseek-v4-pro'
    names = {'Id': 'identifier', 'Name': 'title', 'Director': 'director', 'Creator': 'writers', 'Year': 'year', 'Duration': 'duration', 'Genre': 'genre', 'RatingValue': 'rating', 'RatingCount': 'rating count'}
    view = movie_view('movies_columns')
    res = {c: (collections.Counter({k: v['errors'] for k, v in view[c].items()}), collections.Counter({k: v['repaired'] for k, v in view[c].items()})) for c in CONDS['movies']}
    rows = []
    for group, cols in (('identity', ['Id', 'Name', 'Director', 'Creator']), ('other', ['Year', 'Duration', 'Genre', 'RatingValue', 'RatingCount'])):
        for col in cols:
            rows.append(' & '.join([names[col]] + [f'{res[c][1][col]} / {res[c][0][col]}' for c in CONDS['movies']]) + ' \\\\')
        rows.append('\\midrule')
    rows.pop()
    write('moviescols', '\\begin{table}[t]\n  \\caption{Where knowledge acts on Movies: errors repaired per column by DeepSeek-V4-Pro (repaired / errors). Identity\n  columns above, others below; the fresh table has its own errors.}\n  \\label{tab:moviescols}\n  \\small\n  \\setlength{\\tabcolsep}{4pt}\n  \\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}}lrrrr@{}}\n    \\toprule\n    Column & O & F & W & S \\\\\n    \\midrule\n' + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table}\n')

def construction_table():
    """What was built per dataset: entities and errors of each table, fictitious values, seeds."""
    from .data import load
    from .movies_variants import _names
    ident = {'hospital': ['ProviderNumber', 'HospitalName', 'Address1', 'City', 'ZipCode', 'CountyName', 'PhoneNumber'], 'movies': ['Id', 'Name', 'Director', 'Creator', 'Actors'], 'beers': ['beer-name', 'brewery-name', 'city']}
    key = {'hospital': 'ProviderNumber', 'movies': 'Id', 'beers': 'brewery_id'}
    noun = {'hospital': 'hospitals', 'movies': 'films', 'beers': 'breweries'}

    def stats(cond, ds):
        d, c = load(cond)
        err = int((d != c).values.sum())
        ide = int(sum(((d[k] != c[k]).sum() for k in ident[ds])))
        vals = set()
        for k in ident[ds]:
            for v in c[k]:
                if ds == 'movies' and k in ('Director', 'Creator', 'Actors'):
                    vals.update((('person', n) for n in _names(v)))
                else:
                    vals.add((k, v))
        return (c, err, ide, len(vals))
    rows = []
    src = {'hospital': 'CMS registry, July 2026 release', 'movies': 'IMDb datasets, Sept.\\ 2026', 'beers': 'Wikidata, Sept.\\ 2026'}
    seeds = {'hospital': 3, 'movies': 3, 'beers': 1}
    for ds, label in (('hospital', 'Hospital'), ('movies', 'Movies'), ('beers', 'Beers')):
        if ds == 'movies':
            view = movie_view('construction')
            o, f = (view['movies'], view['movies_fresh'])
            eo, io, vo = (o['errors'], o['identity_errors'], o['values_renamed'])
            ef, i_f = (f['errors'], f['identity_errors'])
            ent_o, ent_f = (f"{o['entities']:,} films", f"{f['entities']:,} films")
            rows.append(' & '.join([label, ent_o, f'{eo:,} ({io})', src[ds], ent_f, f'{ef:,} ({i_f})', f'{vo:,}', str(seeds[ds])]) + ' \\\\')
        else:
            co, eo, io, vo = stats(CONDS[ds][0], ds)
            cf, ef, i_f, _ = stats(CONDS[ds][1], ds)
            shared = len(set(cf[key[ds]]) & set(co[key[ds]])) if ds == 'hospital' else 0
            ent_f = f'{cf[key[ds]].nunique():,} {noun[ds]}' + (f' ({shared} also in O)' if shared else '')
            rows.append(' & '.join([label, f'{co[key[ds]].nunique():,} {noun[ds]}', f'{eo:,} ({io})', src[ds], ent_f, f'{ef:,} ({i_f})', f'{vo:,}', str(seeds[ds])]) + ' \\\\')
    write('construction', "\\begin{table*}[t]\n  \\caption{What \\core{} builds. For each benchmark: the original's entities and error cells (identity columns in\n  parentheses); the fresh table's source, entities and error cells; the number of real identity values each\n  surrogate renames one to one; and the number of construction seeds (fresh table and both surrogates).}\n  \\label{tab:construction}\n  \\small\n  \\begin{tabular*}{\\textwidth}{@{\\extracolsep{\\fill}}l lr llr rc@{}}\n    \\toprule\n    & \\multicolumn{2}{c}{Original (O)} & \\multicolumn{3}{c}{Fresh (F)} & \\multicolumn{1}{c}{W and S} & \\\\\n    \\cmidrule(lr){2-3}\\cmidrule(lr){4-6}\\cmidrule(lr){7-7}\n    Dataset & Entities & Errors & Source & Entities & Errors & Values renamed & Seeds \\\\\n    \\midrule\n" + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table*}\n')

def movies_errors_table():
    """The kinds of Movies errors, counted on the original, and how each controlled table reproduces them."""
    import re
    from .data import load
    from .movies_variants import _fold, _names, people_template, title_recipe
    stats = movie_view('movies_errors')
    n = lambda col: stats['errors_by_column'][col]
    pref, yr = (stats['slug_numbered'], stats['slug_year'])
    ids = range(stats['slug_plain'] + pref + yr)
    kinds = stats['title_recipe_kinds']
    dur_rt, dur_empty = (stats['duration_formatted'], stats['duration_empty'])

    def people(col):
        k = stats['people'][col]
        parts = [f"{k[x]} {('names ' if j == 0 else '')}{x}" for j, x in enumerate((x for x in ('added', 'dropped', 'respelled') if k[x]))]
        return ', '.join(parts) + (f"; {k['emptied']} cells emptied" if k['emptied'] else '')
    rows = [('identifier', n('Id'), f'Rotten Tomatoes slug ({len(ids) - pref - yr} plain, {pref} numbered, {yr} with the year)', "slug of the fresh title, forms at the original's rates", 'slug of the dirty fictitious title, same form'), ('year', n('Year'), "range ``Y$-$1 Y Y$+$1''", 'same range', "the original's cell"), ('title', n('Name'), f'{kinds} edit recipes (capitalization, \\& for \\emph{{and}}, accent, punctuation, subtitle, article)', 'the same edits on a fresh title', 'the same edits on the fictitious title'), ('director', n('Director'), people('Director'), 'copied name by name', 'copied name by name'), ('writers', n('Creator'), people('Creator'), 'copied name by name', 'copied name by name'), ('duration', n('Duration'), f'Rotten Tomatoes format ({dur_rt}) or empty ({dur_empty})', "drawn at the original's rates", "the original's cell"), ('rating', n('RatingValue'), f"score pair ({stats['rating_score_pair']}) or empty ({stats['rating_empty']}); ``.0'' added ({stats['rating_dot0']})", "drawn at the original's rates", "the original's cell"), ('rating count', n('RatingCount'), 'thousands separators on every count $\\geq$ 1,000', 'the same rule', "the original's cell"), ('genre', n('Genre'), 'Rotten Tomatoes genre vocabulary', 'copied slot by slot', "the original's cell")]
    body = '\n'.join(('    ' + ' & '.join([a, f'{b:,}', c_, d_, e]) + ' \\\\' for a, b, c_, d_, e in rows))
    write('movieserrors', '\\begin{table*}[t]\n  \\caption{The ' + f"{stats['total_errors']:,}" + ' errors of Movies by column, and how the controlled tables reproduce them. All but the table-wide\n  formatting rules sit in the ' + str(stats['rt_rows']) + " rows taken from Rotten Tomatoes. ``Copied'' errors are derived from the original\n  cell in the same row (or moved to another Rotten Tomatoes row that can take them); ``drawn'' errors are generated\n  with the rates measured on the original. Slug: the film's name in its Rotten Tomatoes URL; score pair: two Rotten\n  Tomatoes scores such as 5.4/10,6/10; rating count: the number of ratings.}\n  \\label{tab:movieserrors}\n  \\small\n  \\begin{tabular}{@{}lr p{6.4cm} p{3.75cm} p{3.75cm}@{}}\n    \\toprule\n    Column & Errors & In the original & Fresh table & Surrogates \\\\\n    \\midrule\n" + body + '\n    \\bottomrule\n  \\end{tabular}\n\\end{table*}\n')

def checks_table():
    """The acceptance checks run on the controlled tables, by category (results/validate_tables.json)."""
    import re
    checks = [x for x in evidence_json(ROOT / 'results' / 'derived' / 'validate_tables.json') if 'check' in x]
    cats = [('Structure', 'same shape|same clean table|seed \\d+ and seed \\d+|error cells where|non-identity cells'), ('Error kinds and counts', "error kinds|number of errors|x-substitution|in the original's form|people errors only|Id and Year|thousands separators|rebuild from the clean"), ('Error strength', 'characters replaced|strength'), ('Naming and leakage', 'fictitious|real title|read as names|repeat a person|titles do not|titles like|pool'), ('Fresh entities', 'no film|no beer|one city and state|Wikidata'), ('Reproducibility', 'byte for byte')]
    what = {'Structure': 'shape and columns; error cells where the original has them; non-identity cells identical; seeds differ, fresh clean table shared', 'Error kinds and counts': 'per column, kinds and counts as in the original; formatting rules; errors only in the rows that carry them', 'Error strength': 'characters replaced per error cell within a tolerance of the original', 'Naming and leakage': 'one fictitious value per real value and back; no real value reused; no word of a real title; title shapes no closer to the real ones than chance; names look like names', 'Fresh entities': 'no entity of the benchmark; locations checked against sources', 'Reproducibility': 'every table rebuilt byte for byte under two hash seeds'}
    count = collections.Counter()
    for x in checks:
        cat = next((k for k, rx in cats if re.search(rx, x['check'])), None)
        assert cat, x['check']
        count[cat] += 1
    tables = len({x['table'] for x in checks})
    rows = [f'{k} & {count[k]} & {what[k]} \\\\' for k, _ in cats]
    write('checks', '\\begin{table}[t]\n  \\caption{Acceptance checks, run on every controlled table before any model sees it: ' + f'{sum(count.values())}' + ' checks over ' + str(tables) + ' tables.}\n  \\label{tab:checks}\n  \\small\n  \\setlength{\\tabcolsep}{3pt}\n  \\begin{tabularx}{\\columnwidth}{@{}>{\\raggedright\\arraybackslash}p{0.24\\columnwidth}r>{\\raggedright\\arraybackslash}X@{}}\n    \\toprule\n    Category & Checks & What is compared with the original \\\\\n    \\midrule\n' + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabularx}\n\\end{table}\n')

def detection_table():
    """Detection and repair F1 on identity columns, commercial models, Hospital and Movies, O / W / S."""
    from .probe_clean import metrics, total
    cell = lambda d, r: f'{dot2(d)}/{dot2(r)}'
    rows = []
    for tag, name in COMMERCIAL:
        out = [SHORT[name]]
        for ds in ('hospital', 'movies'):
            for k in (0, 2, 3):
                m = metrics(total(chunks(tag, CONDS[ds][k]), G))
                out.append(cell(m['detect_f1'], m['repair_f1']))
        rows.append(' & '.join(out) + ' \\\\')
    write('detection', '\\begin{table}[t]\n  \\caption{Detection and repair diverge on surrogate identity columns. Detection F1 /\n  repair F1 on identity columns (detection counts a corrupted cell as found whatever value is proposed).}\n  \\label{tab:detection}\n  \\small\n  \\setlength{\\tabcolsep}{3pt}\n  \\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}}l ccc ccc@{}}\n    \\toprule\n    & \\multicolumn{3}{c}{Hospital} & \\multicolumn{3}{c}{Movies} \\\\\n    \\cmidrule(lr){2-4}\\cmidrule(l){5-7}\n    Model & O & W & S & O & W & S \\\\\n    \\midrule\n' + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table}\n')

def decoding_table():
    """Hospital syllable surrogate: corrupted identity cells by what could restore them, and how many each model
    repairs. A pseudo-word is 'unique' when the surrogate's 24 syllables allow exactly one restoration."""
    import functools
    from .data import load
    from .hospital_variants import SYL
    from .probe_clean import IDENTITY, norm, parse
    generic = {'hospital', 'regional', 'medical', 'center', 'memorial', 'health', 'street', 'avenue', 'road', 'drive', 'blvd'}

    @functools.lru_cache(None)
    def decodings(w):
        if not w:
            return frozenset({''})
        out = set()
        for syl in SYL:
            if len(syl) <= len(w) and all((a == b or a == 'x' for a, b in zip(w[:len(syl)], syl))):
                out |= {syl + rest for rest in decodings(w[len(syl):])}
        return frozenset(out)

    def kind(dv, cv):
        diff = [(a, b) for a, b in zip(dv.lower().split(), cv.lower().split()) if a != b]
        if len(dv.split()) != len(cv.split()) or not diff:
            return None
        kinds = set()
        for a, b in diff:
            if b.isdigit():
                kinds.add('digit')
            elif b in generic:
                kinds.add('generic')
            else:
                kinds.add('unique' if decodings(a) == {b} else 'ambiguous')
        for k in ('digit', 'ambiguous', 'unique', 'generic'):
            if k in kinds:
                return k
    cond = 'hospital_surrogate'
    dirty, clean = load(cond)
    ident = IDENTITY['hospital']
    cls = {(i, c): kind(dirty.at[i, c], clean.at[i, c]) for i in range(len(clean)) for c in ident if dirty.at[i, c] != clean.at[i, c]}
    order = ['unique', 'ambiguous', 'generic', 'digit']
    n = collections.Counter((v for v in cls.values() if v))

    def repaired(tag):
        got = collections.Counter()
        for ch in chunks(tag, cond):
            pred = {}
            for p in parse(ch['output']):
                try:
                    r = int(p['row']) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= r < len(ch['rows']) and str(p['column']) in ident:
                    pred[ch['rows'][r], str(p['column'])] = str(p['value']).strip()
            for key, v in pred.items():
                if cls.get(key) and norm(v) == norm(clean.at[key]) and (norm(v) != norm(dirty.at[key])):
                    got[cls[key]] += 1
        return got
    rows = [' & '.join([name] + [str(repaired(tag)[k]) for k in order]) + ' \\\\' for tag, name in COMMERCIAL]
    opn = [repaired(tag) for tag, _ in OPEN]
    span = lambda lo, hi: str(lo) if lo == hi else f'{lo}--{hi}'
    rows.append(' & '.join(['Open models'] + [span(min((o[k] for o in opn)), max((o[k] for o in opn))) for k in order]) + ' \\\\')
    head = ' & '.join(['Model'] + [f'{lab} ({n[k]})' for k, lab in zip(order, ['Unique', 'Ambig.', 'Generic', 'Digits'])])
    write('decoding', "\\begin{table}[t]\n  \\caption{GPT-6.1-Sol repairs more uniquely decodable syllable names. Hospital S identity errors repaired\n  by category (cell counts in headers): Unique and Ambig. use the constructor's 24-syllable inventory;\n  Generic denotes English terms such as \\emph{hospital}; Digits denotes numeric tokens. The categories\n  cover 217 of 219 errors, excluding two address-spacing errors.}\n  \\label{tab:decoding}\n  \\small\n  \\setlength{\\tabcolsep}{4pt}\n  \\begin{tabular}{@{}lrrrr@{}}\n    \\toprule\n    " + head + ' \\\\\n    \\midrule\n' + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular}\n\\end{table}\n')

def seeds_table():
    rows = []
    for tag, name in COMMERCIAL + OPEN:
        cells = [SHORT[name]]
        for base, kinds in (('hospital', ('entity', 'spelling', 'total')), ('movies', ('entity', 'paired'))):
            per = []
            for s_ in (0, 1, 2):
                o, f, w, sy = (f1_of(chunks(tag, seeded(c, s_)), G) for c in CONDS[base])
                per.append({'entity': f - w, 'spelling': w - sy, 'total': o - sy, 'paired': o - w})
            for k in kinds:
                lo, hi = (min((p[k] for p in per)), max((p[k] for p in per)))
                assert lo > -0.005, (name, k, lo)
                lo, hi = (dot2(max(lo, 0)), dot2(hi))
                cells.append(lo if lo == hi else f'{lo}--{hi}')
        rows.append(' & '.join(cells) + ' \\\\')
    rows.insert(len(COMMERCIAL), '\\midrule')
    write('seeds', "\\begin{table}[t]\n  \\caption{Hospital's total knowledge effect varies little across construction seeds. Ranges over three seeds\n  (identity columns; seed 0 in Table~\\ref{tab:main}). Fresh clean records are fixed across seeds.}\n  \\label{tab:seeds}\n  \\small\n  \\setlength{\\tabcolsep}{2.5pt}\n  \\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}}l ccc cc@{}}\n    \\toprule\n    & \\multicolumn{3}{c}{Hospital} & \\multicolumn{2}{c}{Movies} \\\\\n    \\cmidrule(lr){2-4}\\cmidrule(l){5-6}\n    Model & F$-$W & W$-$S & O$-$S & F$-$W & O$-$W \\\\\n    \\midrule\n" + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table}\n')

def beers_table():
    from .scale import beers_city
    fam = Family()
    rows, signs = ([], [])
    for tag, name in COMMERCIAL + OPEN:
        b = [chunks(tag, c) for c in CONDS['beers']]
        city = beers_city(tag)
        rep = ' / '.join((str(city[k]['repaired']) for k in ('original', 'fresh', 'words', 'syllable')))
        p = city['words_vs_syllable']['sign_test_p']
        signs.append(p)
        rows.append(' & '.join([name] + [f2(f1_of(x, G)) for x in b] + [fam.add(b[0], b[3], True), rep, f'@@p{len(signs) - 1}@@']) + ' \\\\')
    body, n_tests = fam.render('\n'.join(('    ' + r for r in rows)))
    adj = holm(signs)
    for i in range(len(signs)):
        body = body.replace(f'@@p{i}@@', f'{adj[i]:.3f}')
    write('beers', "\\begin{table}[t]\n  \\caption{Qwen3.8-Max has a positive knowledge effect on Beers' formatting errors; the other models show no\n  significant positive effect. Beers, whose errors are all formatting\n  errors: repair F1 on identity columns, total knowledge O$-$S, city\n  errors repaired (of 127) in O / F / W / S, and a sign test over chunks comparing W with S ($p$ Holm-corrected over the\n  models). $^{*}$F is descriptive: the fresh table differs in entity concentration and alcohol-content distribution.\n  Knowledge comparisons use O, W and S. $^\\dagger$ as in Table~\\ref{tab:main}, corrected over this table's " + str(n_tests) + ' differences.}\n  \\label{tab:beers}\n  \\small\n  \\setlength{\\tabcolsep}{2pt}\n  \\begin{tabular}{@{}lcccccrr@{}}\n    \\toprule\n    Model & O & F$^{*}$ & W & S & O$-$S & Cities repaired & $p$ \\\\\n    \\midrule\n' + body + '\n    \\bottomrule\n  \\end{tabular}\n\\end{table}\n')

def aligned_table():
    from .aligned import score
    al = ARCHIVE / 'aligned'
    e5 = evidence_json(ARCHIVE / 'e5' / 'summary.json')
    e4 = evidence_json(ARCHIVE / 'e4' / 'summary.json')
    rows = []
    for base, label in (('hospital', 'Hospital'), ('movies', 'Movies'), ('beers', 'Beers')):
        conds = CONDS[base]
        llm = [f1_of(score(c, evidence_json(al / f'custom_deepseek_deepseek-v4-pro__{c}.json')), G) for c in conds]
        bar = []
        for c in conds:
            runs = sorted(evidence_paths(al, f'baran__{c}__run*.json')) or [al / f'baran__{c}.json']
            bar.append(sum((f1_of(score(c, evidence_json(f)), G) for f in runs)) / len(runs))
        whole = [e5.get(f'{c}|perfect', {}).get('identity_repair_f1') for c in conds]
        tab = [e4[c]['identity']['repair_f1'] for c in conds]
        fmt = lambda v: ' & '.join(('---' if x is None else f2(x) for x in v))
        rows.append('\\multicolumn{5}{@{}l}{\\emph{' + label + '}} \\\\')
        rows += [f'\\quad DeepSeek, aligned & {fmt(llm)} \\\\', f'\\quad Baran, aligned & {fmt(bar)} \\\\', f'\\quad Baran, whole table & {fmt(whole)} \\\\', f'\\quad TabClean & {fmt(tab)} \\\\']
    write('aligned', '\\begin{table}[t]\n  \\caption{DeepSeek-V4-Pro retains a fresh--words gap on Hospital and Movies with labels and error positions.\n  Whole-table Baran and TabClean scores vary little across conditions. Repair F1 on identity columns.\n  Aligned: the same chunks with 20 labeled tuples and the error\n  positions (Baran: mean of three seeded runs). Whole table: Baran with perfect detection, mean of three seeds.\n  TabClean: DeepSeek-V4-Pro backbone, development rows excluded.}\n  \\label{tab:aligned}\n  \\small\n  \\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}}l cccc@{}}\n    \\toprule\n    Method & O & F & W & S \\\\\n    \\midrule\n' + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table}\n')

def p1_table():
    models = [('custom_deepseek_deepseek-v4-pro', 'DeepSeek-V4-Pro'), ('local_mlx-community_OLMo-2-1124-7B-Instruct-4bit', 'OLMo-2-7B-Instruct'), ('localbase', 'OLMo-2-7B (base)')] + OPEN
    modes = [('clean', 'anon'), ('dirty', 'anon'), ('clean', 'named'), ('dirty', 'named'), ('dirty', 'anon__err')]
    rows = []
    for tag, name in models:
        best, leaks, hard = ([], 0, 0)
        for src, mode in modes:
            vals = []
            for f in evidence_glob(str(ARCHIVE / 'p1' / f'{tag}__*__{src}__{mode}.json')):
                s = evidence_json(Path(f))['summary']
                if s.get('acc_hard') is not None:
                    vals.append(s['acc_hard'])
                if src == 'dirty':
                    n = s.get('leak_hard_cells') or 0
                    hard += n
                    leaks += round((s.get('leak_hard_rate') or 0) * n)
            best.append(f'{max(vals):.3f}' if vals else '---')
        rows.append(' & '.join([name] + best + [f'{leaks} / {hard}']) + ' \\\\')
    write('p1', '\\begin{table}[t]\n  \\caption{Row continuation provides no positive evidence of benchmark memorization in the tested models.\n  Row-continuation probe:\n  the highest share of hard cells (those no structural baseline guesses) continued\n  correctly over the datasets, by context (clean or dirty table; dataset name withheld or given; rows with errors only),\n  and how many hard erroneous cells were continued with their clean value given the dirty context.}\n  \\label{tab:p1}\n  \\small\n  \\setlength{\\tabcolsep}{2.5pt}\n  \\begin{tabular}{@{}lcccccr@{}}\n    \\toprule\n    & \\multicolumn{2}{c}{Anonymous} & \\multicolumn{2}{c}{Named} & Error & Clean value \\\\\n    \\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\n    Model & clean & dirty & clean & dirty & rows & leaked \\\\\n    \\midrule\n' + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular}\n\\end{table}\n')

def near_table():
    rows = []
    for tag, name in COMMERCIAL + OPEN:
        cells = [name]
        for ds in ('movies', 'hospital', 'beers'):
            s = evidence_json(ARCHIVE / 'near' / f'{tag}__{ds}__summary.json')
            k = known_key_rates(ROOT / 'data/final/_near', ds, tag, s)
            for p in ('standard', 'evidence') if ds == 'movies' else ('standard',):
                r = k[f'real|1|{p}']
                cells.append(f"{r['rate']:.3f} [{r['ci'][0]:.3f}, {r['ci'][1]:.3f}]" if ds == 'movies' else f"{r['rate']:.3f}")
            if ds == 'movies':
                cells.insert(1, str(k['real|1|standard']['entities']))
        rows.append(' & '.join(cells) + ' \\\\')
    write('near', "\\begin{table*}[t]\n  \\caption{Director rewrites toward real-world credits are frequent, while city rewrites are rare.\n  Rates use each model's known subset of the common target pool, with one row per target.\n  Movies: a Director edit matching at least one real credit, with standard and table-evidence\n  prompts (95\\% entity-bootstrap intervals). Hospital and Beers: city edits matching the real\n  city, standard prompt. Rates and interval endpoints retain the source precision.}\n  \\label{tab:near}\n  \\small\n  \\begin{tabular}{@{}lccccc@{}}\n    \\toprule\n    & & \\multicolumn{2}{c}{Movies, director} & Hospital & Beers \\\\\n    \\cmidrule(lr){3-4}\n    Model & Known films & Standard & Table evidence only & location & location \\\\\n    \\midrule\n" + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular}\n\\end{table*}\n')

def conflict_counts_table():
    records = read_witnesses()['near']
    rows = []
    for tag, name in COMMERCIAL + OPEN:
        record = records[tag]
        count, den = (collections.Counter(), collections.Counter())
        for e in record['events']:
            typ, support, prompt = e['setting'].split('|')
            if not e['known'] or typ not in ('real', 'control') or support != '1':
                continue
            cells = [c for c in e['cells'] if c['column'] == 'Director']
            den[typ, prompt] += len(cells)
            count[typ, prompt] += sum((c['to_fact'] if typ == 'real' else c['changed'] for c in cells))
            if typ == 'control' and any((c['to_fact'] for c in cells)):
                raise ValueError('Control fact rewrite')
        settings = [(t, p) for t in ('real', 'control') for p in ('standard', 'evidence')]
        if any((den[s] != record['summary']['screened_known']['known'] for s in settings)):
            raise ValueError('Incomplete anonymous target exposure')
        rows.append(' & '.join([name] + [f'{count[s]}/{den[s]}' for s in settings]) + ' \\\\')
    write('conflictcounts', "\\begin{table}[t]\n  \\caption{Director rewrite counts among known films ($n/N$). Exact-name targets count edits\n  matching a real-world director credit. Surrogate controls count any Director change;\n  none matches the paired film's real credit.}\n  \\label{tab:conflictcounts}\n  \\small\n  \\setlength{\\tabcolsep}{3pt}\n  \\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}}lrrrr@{}}\n    \\toprule\n    & \\multicolumn{2}{c}{Exact-name target} & \\multicolumn{2}{c}{Surrogate control} \\\\\n    \\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\n    Model & Standard & Evidence & Standard & Evidence \\\\\n    \\midrule\n" + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table}\n')

def rayyan_table():
    rows_ = evidence_json(ROOT / 'results' / 'derived' / 'rayyan_audit.json')
    by = collections.defaultdict(list)
    for r in rows_:
        by[r['stratum']].append(r)
    names = {'日期': 'Year', '编码乱码': 'Changed words', '缺失写成-1': 'Vol./issue', '页码': 'Pages', 'ISSN': 'ISSN'}
    rows, strata = ([], {})
    for s, rs in by.items():
        found = [r for r in rs if r.get('pmid') and 'clean_ok' in r]
        bad = [not r['clean_ok'] for r in found]
        strata[s] = (rs[0]['population'], bad)
        dirty = '---' if s == '编码乱码' else str(sum((r['dirty_ok'] for r in found)))
        rows.append(f"{names.get(s, s)} & {rs[0]['population']} & {len(rs)} & {len(found)} & {sum(bad)} & {dirty} \\\\")
    N = sum((p for p, _ in strata.values()))
    est = sum((p * sum(b) / len(b) for p, b in strata.values())) / N
    rng = random.Random(0)
    bs = sorted((sum((p * sum((rng.choice(b) for _ in b)) / len(b) for p, b in strata.values())) / N for _ in range(5000)))
    lo, hi = (bs[124], bs[4874])
    write('rayyan', "\\begin{table}[t]\n  \\caption{Rayyan's stratified reference checks. $N_h$: error cells; $n_h$: sampled cells;\n  $m_h$: title-matched cells; $b_h$: failed reference checks; $d_h$: passed dirty checks.\n  The weighted rate of failed reference checks is " + f'{100 * est:.1f}\\% (95\\% interval: {100 * lo:.1f}--{100 * hi:.1f}\\%)' + ' using the ' + str(N) + '-cell type weights.\n  A dash denotes an unassessed dirty-side check.}\n  \\label{tab:rayyan}\n  \\small\n  \\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}}lrrrrr@{}}\n    \\toprule\n    Check & $N_h$ & $n_h$ & $m_h$ & $b_h$ & $d_h$ \\\\\n    \\midrule\n' + '\n'.join(('    ' + r for r in rows)) + '\n    \\bottomrule\n  \\end{tabular*}\n\\end{table}\n')

def main() -> None:
    main_table()
    example_table()
    construction_table()
    movies_errors_table()
    checks_table()
    movies_columns_table()
    detection_table()
    decoding_table()
    seeds_table()
    beers_table()
    counts_table()
    aligned_table()
    p1_table()
    near_table()
    conflict_counts_table()
    rayyan_table()
if __name__ == '__main__':
    main()
