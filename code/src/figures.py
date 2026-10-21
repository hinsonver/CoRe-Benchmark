from .core_runtime import evidence_json, evidence_glob, evidence_paths, movie_view, read_witnesses, public_mode
import os
from .screening import known_key_rates
'Main paper figures (static, print): PDF + 300-dpi PNG + the plotted numbers as CSV.\n\n  fig1_decomposition  P2 repair F1 on the four conditions, per dataset, 95% bootstrap CI\n  fig2_year_range     Movies "Y-1 Y Y+1" year cells: which year the model picks, and accuracy\n                      against the "always take the middle year" rule\n  fig3_aligned        LLM vs Baran under the same view, labels and task (repair only)\n  fig4_near_entity    share of target cells rewritten to the famous entity\'s fact\n  fig5_rayyan         Rayyan ground truth vs PubMed, by error type\n  fig6_scale          model-scale gradient: Hospital four conditions per model, and the Movies\n                      near-entity rewrite rate per model (entities that model knows)\n\nColors: the reference categorical slots in fixed order (validated: the 4-slot set passes the\nadjacent gates, the 3-slot set the all-pairs gates; aqua and yellow sit below 3:1 on the surface,\nso every bar carries a visible value label and each figure has a CSV table).\nUsage: .venv/bin/python -m src.figures   (writes figures/)\n'
import csv
import json
import random
import re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .data import ARCHIVE, BUILD, ROOT, load
from .probe_clean import metrics, norm, parse
FIG = Path(os.environ.get('CORE_FIGURE_DIR', BUILD / 'figures')).resolve()
MODEL = 'custom_deepseek_deepseek-v4-pro'
SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']
(INK, INK2, MUTED, GRID, AXIS, SURFACE) = ('#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7', '#fcfcfb')
CONDITIONS = ['Original', 'Fresh', 'Words surrogate', 'Syllable surrogate']
BASES = {'hospital': ['hospital', 'hospital_fresh', 'hospital_surrogatewords', 'hospital_surrogate'], 'movies': ['movies', 'movies_fresh', 'movies_surrogatewords', 'movies_surrogate'], 'beers': ['beers_orig', 'beers_fresh', 'beers_surrogatewords', 'beers_surrogate']}
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'], 'font.size': 8, 'axes.titlesize': 8.5, 'axes.titleweight': 'bold', 'axes.labelsize': 8, 'axes.edgecolor': AXIS, 'axes.linewidth': 0.8, 'axes.labelcolor': INK2, 'axes.titlecolor': INK, 'xtick.color': INK2, 'ytick.color': INK2, 'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6, 'axes.axisbelow': True, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.facecolor': 'white', 'axes.facecolor': 'white', 'legend.frameon': False, 'legend.fontsize': 7.5, 'pdf.fonttype': 42})

def save(fig, name: str, rows: list[dict]) -> None:
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f'{name}.pdf', bbox_inches='tight', pad_inches=0.02)
    fig.savefig(FIG / f'{name}.png', dpi=300, bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)
    with open(FIG / f'{name}.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
(COL, PAGE) = (3.33, 7.0)
SMALL = {'font.size': 7, 'axes.titlesize': 7.2, 'axes.labelsize': 6.8, 'xtick.labelsize': 6.4, 'ytick.labelsize': 6.4, 'legend.fontsize': 6.4, 'legend.handlelength': 1.2, 'legend.columnspacing': 1.0}

def f1_ci(chunks: list[dict], group: str, n: int=2000) -> tuple[float, float, float]:
    """Repair F1 and its 95% bootstrap interval over chunks."""

    def f1(cs):
        tot = {k: sum((c['counts'][group][k] for c in cs)) for k in ('errors', 'predicted', 'repaired', 'detected')}
        return metrics(tot)['repair_f1']
    rng = random.Random(0)
    bs = sorted((f1([rng.choice(chunks) for _ in chunks]) for _ in range(n)))
    return (f1(chunks), bs[int(0.025 * n)], bs[int(0.975 * n) - 1])

def bars(ax, values, errs, labels, colors, ymax=1.0):
    """Thin bars from one baseline, value label above the whisker."""
    x = range(len(values))
    lo = [v - e[0] for (v, e) in zip(values, errs)]
    hi = [e[1] - v for (v, e) in zip(values, errs)]
    ax.bar(x, values, width=0.62, color=colors, edgecolor='white', linewidth=1.5, zorder=2)
    ax.errorbar(x, values, yerr=[lo, hi], fmt='none', ecolor=INK2, elinewidth=0.8, capsize=2, zorder=3)
    for (xi, v, e) in zip(x, values, errs):
        ax.text(xi, e[1] + 0.025 * ymax, f'{v:.2f}', ha='center', va='bottom', fontsize=7, color=INK)
    ax.set_xticks(list(x), labels, rotation=0)
    ax.set_ylim(0, ymax * 1.12)
    ax.grid(axis='x', visible=False)

def fig1() -> None:
    """Teaser, one column: DeepSeek-V4-Pro in the four conditions on three benchmarks."""
    panels = [('hospital', 'identity', 'Hospital'), ('movies', 'identity', 'Movies'), ('beers', 'all', 'Beers\n(formatting control)')]
    rows = []
    with plt.rc_context(SMALL):
        (fig, axes) = plt.subplots(1, 3, figsize=(COL, 1.65), sharey=True)
        for (ax, (base, group, title)) in zip(axes, panels):
            (vals, errs) = ([], [])
            for (cond, name) in zip(BASES[base], CONDITIONS):
                ch = evidence_json(ARCHIVE / 'p2' / f'{MODEL}__{cond}__k20__spread.json')['chunks']
                (v, lo, hi) = f1_ci(ch, group)
                vals.append(v)
                errs.append((lo, hi))
                rows.append({'dataset': base, 'columns': group, 'condition': name, 'repair_f1': round(v, 3), 'ci_low': round(lo, 3), 'ci_high': round(hi, 3)})
            display_order = [0, 2, 3, 1]
            x = [0, 1, 2, 3.6]
            shown_vals = [vals[i] for i in display_order]
            shown_errs = [errs[i] for i in display_order]
            ax.bar(x, shown_vals, width=0.72, color=[SERIES[i] for i in display_order], edgecolor='white', linewidth=0.8, zorder=2)
            ax.errorbar(x, shown_vals, yerr=[[v - e[0] for (v, e) in zip(shown_vals, shown_errs)], [e[1] - v for (v, e) in zip(shown_vals, shown_errs)]], fmt='none', ecolor=INK2, elinewidth=0.6, capsize=1.2, zorder=3)
            for (xi, v, e) in zip(x, shown_vals, shown_errs):
                ax.text(xi, e[1] + 0.03, f'{v:.2f}'[1:] if v < 1 else '1.0', ha='center', va='bottom', fontsize=5.6, color=INK)
            ax.set_xticks(x, ['O', 'W', 'S', '$F^{*}$' if base == 'beers' else 'F'])
            ax.text(1, -0.28, 'Paired', transform=ax.get_xaxis_transform(), ha='center', fontsize=5.6, color=INK2)
            ax.text(3.6, -0.28, 'Fresh', transform=ax.get_xaxis_transform(), ha='center', fontsize=5.6, color=INK2)
            ax.set_ylim(0, 1.13)
            ax.set_yticks([0, 0.5, 1.0])
            ax.grid(axis='x', visible=False)
            ax.set_title(title, loc='left', pad=3)
        axes[0].set_ylabel('Repair F1')
        fig.tight_layout(pad=0.3, w_pad=0.6)
        save(fig, 'fig1_decomposition', rows)

def fig2() -> None:
    """One column: which year the model writes for the 190 "Y-1 Y Y+1" cells, and how often it is right."""
    conds = [('movies', 'Real films'), ('movies_surrogatewords', 'Words surr.'), ('movies_surrogate', 'Syllable surr.')]
    cats = ['middle year', 'first year', 'other / unchanged']
    view = movie_view('movies_year')
    data = [{k: view[c][k] for k in cats} for (c, _) in conds]
    acc = [view[c]['ok'] / view[c]['n'] for (c, _) in conds]
    rule = [view[c]['middle_rule_ok'] / view[c]['n'] for (c, _) in conds]
    with plt.rc_context(SMALL):
        (fig, ax) = plt.subplots(figsize=(COL, 1.3))
        y = list(range(len(conds)))[::-1]
        left = [0] * len(conds)
        for (k, color) in zip(cats, SERIES[:3]):
            w = [d[k] for d in data]
            ax.barh(y, w, left=left, color=color, edgecolor='white', linewidth=0.8, height=0.62, label=k, zorder=2)
            for (yi, l, wi) in zip(y, left, w):
                if wi >= 16:
                    ax.text(l + wi / 2, yi, str(wi), ha='center', va='center', fontsize=6, color='white' if color == SERIES[0] else INK)
            left = [l + wi for (l, wi) in zip(left, w)]
        for (yi, a) in zip(y, acc):
            ax.text(196, yi, f'{a:.2f}', ha='left', va='center', fontsize=6.4, color=INK, fontweight='bold')
        ax.text(196, max(y) + 0.62, 'correct', ha='left', va='center', fontsize=6, color=MUTED)
        ax.set_yticks(y, [c[1] for c in conds])
        ax.set_xlim(0, 214)
        ax.set_xticks([0, 50, 100, 150, 190])
        ax.set_ylim(-0.55, max(y) + 0.85)
        ax.set_xlabel('Year cells written as "Y$-$1 Y Y$+$1" (190 rows)')
        ax.grid(axis='y', visible=False)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y', length=0)
        ax.legend(loc='lower center', bbox_to_anchor=(0.42, 1.0), ncol=3, frameon=False, borderaxespad=0.2)
        fig.tight_layout(pad=0.3)
        save(fig, 'fig2_year_range', [{'condition': c[1], **d, 'accuracy': round(a, 3), 'middle_rule_accuracy': round(r, 3)} for (c, d, a, r) in zip(conds, data, acc, rule)])

def fig3() -> None:
    """One column: DeepSeek-V4-Pro zero-shot and aligned, Baran aligned, on Hospital and Movies identity columns."""
    from .aligned import score
    panels = [('hospital', 'identity', 'Hospital'), ('movies', 'identity', 'Movies')]
    rows = []
    with plt.rc_context(SMALL):
        (fig, axes) = plt.subplots(1, 2, figsize=(COL, 1.6), sharey=True)
        for (ax, (base, group, title)) in zip(axes, panels):
            series = {'DeepSeek-V4-Pro, aligned': [], 'Baran, aligned': [], 'DeepSeek-V4-Pro, zero-shot': []}
            for cond in BASES[base]:
                aligned = ARCHIVE / 'aligned'
                llm = score(cond, evidence_json(aligned / f'{MODEL}__{cond}.json'))
                runs = sorted(evidence_paths(aligned, f'baran__{cond}__run*.json')) or [aligned / f'baran__{cond}.json']
                bars = [f1_ci(score(cond, evidence_json(f)), group) for f in runs]
                mean = sum((b[0] for b in bars)) / len(bars)
                bar = (mean, bars[0][1] + mean - bars[0][0], bars[0][2] + mean - bars[0][0])
                p2 = evidence_json(ARCHIVE / 'p2' / f'{MODEL}__{cond}__k20__spread.json')['chunks']
                for (k, v) in zip(series, (f1_ci(llm, group), bar, f1_ci(p2, group))):
                    series[k].append(v)
            x = list(range(4))
            for ((k, vals), color, mk) in zip(series.items(), (SERIES[0], SERIES[1], SERIES[2]), ('o', 's', 'o')):
                v = [t[0] for t in vals]
                ax.plot(x, v, color=color, linewidth=1.4, marker=mk, markersize=3.6, markeredgecolor='white', markeredgewidth=0.8, zorder=2, label=k)
                ax.errorbar(x, v, yerr=[[t[0] - t[1] for t in vals], [t[2] - t[0] for t in vals]], fmt='none', ecolor=color, elinewidth=0.6, capsize=1.2, zorder=2)
                for (c, t) in zip(CONDITIONS, vals):
                    rows.append({'dataset': base, 'series': k, 'condition': c, 'repair_f1': round(t[0], 3), 'ci_low': round(t[1], 3), 'ci_high': round(t[2], 3)})
            ax.set_xticks(x, ['O', 'F', 'W', 'S'])
            ax.set_xlim(-0.3, 3.3)
            ax.set_ylim(0, 1.05)
            ax.set_yticks([0, 0.5, 1.0])
            ax.set_title(title, loc='left', pad=3)
        axes[0].set_ylabel('Repair F1')
        (h, l) = axes[0].get_legend_handles_labels()
        fig.legend(h, l, loc='upper center', ncol=2, bbox_to_anchor=(0.54, 1.02), frameon=False)
        fig.tight_layout(pad=0.3, w_pad=0.6, rect=(0, 0, 1, 0.8))
        save(fig, 'fig3_aligned', rows)

def fig4() -> None:
    """Directed fact/name rewrites by DeepSeek-V4-Pro; one row per target, entity-bootstrap CIs."""
    items = [('movies', 'real|1', 'Film, other director'), ('movies', 'near|1', 'Film title, one letter off'), ('hospital', 'near|1', 'Hospital name, one letter off'), ('beers', 'near|1', 'Brewery name, one letter off'), ('beers', 'real|1', 'Brewery, other city'), ('hospital', 'real|1', 'Hospital, other city')]
    rows = []
    with plt.rc_context(SMALL):
        (fig, ax) = plt.subplots(figsize=(COL, 2.4))
        y = [6, 2, 1, 0, 5, 4]
        for (off, (prompt, label, color)) in zip((0.16, -0.16), (('standard', 'standard prompt', SERIES[0]), ('evidence', 'table-evidence prompt', SERIES[1]))):
            (vs, lo, hi) = ([], [], [])
            for (ds, key, name) in items:
                s_ = evidence_json(ARCHIVE / 'near' / f'{MODEL}__{ds}__summary.json')['key_rates']
                r = s_[f'{key}|{prompt}']
                vs.append(r['rate'])
                lo.append(r['ci'][0])
                hi.append(r['ci'][1])
                rows.append({'item': name, 'prompt': prompt, 'rate': r['rate'], 'ci_low': r['ci'][0], 'ci_high': r['ci'][1], 'entities': r['entities']})
            yy = [v + off for v in y]
            ax.errorbar(vs, yy, xerr=[[v - l for (v, l) in zip(vs, lo)], [h - v for (v, h) in zip(vs, hi)]], fmt='none', ecolor=color, elinewidth=0.8, capsize=1.5, zorder=2)
            ax.scatter(vs, yy, s=14, color=color, edgecolor='white', linewidth=0.7, zorder=3, label=label)
            for (v, h, yi) in zip(vs, hi, yy):
                ax.text(max(h, v) + 0.02, yi, f'{v:.3f}', va='center', fontsize=5.8, color=INK)
        ax.set_yticks(y, [i[2] for i in items])
        ax.set_xlim(0, 1.18)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_ylim(-0.6, 7.15)
        ax.text(0.0, 6.75, 'Attribute rewrites', fontsize=6.4, fontweight='bold', color=INK)
        ax.text(0.0, 2.75, 'Name restoration', fontsize=6.4, fontweight='bold', color=INK)
        ax.axhline(3.35, color=AXIS, linewidth=0.7, linestyle=(0, (3, 2)), zorder=1)
        ax.set_xlabel('Rate of matching rewrites')
        ax.grid(axis='y', visible=False)
        ax.tick_params(axis='y', length=0)
        ax.legend(loc='lower center', bbox_to_anchor=(0.3, 1.0), ncol=2, frameon=False, borderaxespad=0.2)
        fig.tight_layout(pad=0.3)
        save(fig, 'fig4_near_entity', rows)

def fig5() -> None:
    """Field-specific checks; retain archived CSV and separate unassessed display state."""
    audit = evidence_json(ROOT / 'results' / 'derived' / 'rayyan_audit.json')
    names = {'日期': 'Date (722)', '编码乱码': 'Encoding (107)', '缺失写成-1': 'Missing as "$-$1" (75)', '页码': 'Pagination (32)', 'ISSN': 'ISSN (12)'}
    axis_names = ['Year (722)', 'Encoding (107)', 'Presence (75)', 'Pages (32)', 'ISSN (12)']
    (rows, display_rows, labels, wrong, dirty_ok, ns) = ([], [], [], [], [], [])
    for (key, name) in names.items():
        rs = [r for r in audit if r['stratum'] == key and r.get('pmid')]
        w = sum((not r['clean_ok'] for r in rs))
        dk = sum((r['dirty_ok'] for r in rs))
        labels.append(name)
        wrong.append(w / len(rs))
        dirty_ok.append(dk / len(rs))
        ns.append((w, dk, len(rs)))
        assessed = key != '编码乱码'
        display_rows.append({'stratum': key, 'matched_cells': len(rs), 'reference_check_failures': w, 'dirty_assessed': assessed, 'dirty_check_passes': dk if assessed else '', 'dirty_display': f'{dk}/{len(rs)}' if assessed else 'not assessed'})
        rows.append({'error_type': name, 'checked': len(rs), 'ground_truth_wrong': w, 'dirty_value_right': dk})
    with plt.rc_context(SMALL):
        (fig, ax) = plt.subplots(figsize=(COL, 1.95))
        y = list(range(len(labels)))[::-1]
        h = 0.36
        ax.barh([v + h / 2 for v in y], wrong, height=h, color=SERIES[0], edgecolor='white', linewidth=0.6, label='Reference check fails', zorder=2)
        measured = [i for (i, r) in enumerate(display_rows) if r['dirty_assessed']]
        ax.barh([y[i] - h / 2 for i in measured], [dirty_ok[i] for i in measured], height=h, color=SERIES[1], edgecolor='white', linewidth=0.6, label='Dirty check passes', zorder=2)
        for (i, (yi, (w, dk, n))) in enumerate(zip(y, ns)):
            ax.text(w / n + 0.015, yi + h / 2, f'{w}/{n}', va='center', fontsize=5.6, color=INK)
            if display_rows[i]['dirty_assessed']:
                ax.text(dk / n + 0.015, yi - h / 2, f'{dk}/{n}', va='center', fontsize=5.6, color=INK)
            else:
                ax.text(0.02, yi - h / 2, 'not assessed', va='center', fontsize=5.6, color=INK2)
        ax.set_ylim(-0.6, len(labels) - 0.4)
        ax.set_yticks(y, axis_names)
        ax.set_xlim(0, 1.17)
        ax.set_xticks([0, 0.5, 1.0], ['0', '50%', '100%'])
        ax.grid(axis='y', visible=False)
        ax.tick_params(axis='y', length=0)
        ax.set_xlabel('Share of title-matched cells')
        ax.legend(loc='lower center', bbox_to_anchor=(0.36, 1.0), ncol=1, frameon=False, borderaxespad=0.2)
        fig.tight_layout(pad=0.3)
        save(fig, 'fig5_rayyan', rows)
    with open(FIG / 'fig5_rayyan_display.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(display_rows[0]))
        writer.writeheader()
        writer.writerows(display_rows)

def fig6() -> None:
    """Full width, short: Hospital identity columns in the four conditions, open-weight models by size, then the
    commercial models."""
    from .scale import CONDS, MODELS, chunks
    models = [m for m in MODELS if m[0] != 'local_olmo2-7b']
    n_open = sum((m[0].startswith('local_') for m in models))
    rows = []
    with plt.rc_context(SMALL):
        (fig, ax) = plt.subplots(figsize=(PAGE, 1.55))
        w = 0.2
        for (k, (name, color)) in enumerate(zip(CONDITIONS, SERIES)):
            (xs, vs, los, his) = ([], [], [], [])
            for (i, (tag, model, _)) in enumerate(models):
                (v, lo, hi) = f1_ci(chunks(tag, CONDS['hospital'][k]), 'identity')
                xs.append(i + (k - 1.5) * w)
                vs.append(v)
                los.append(v - lo)
                his.append(hi - v)
                rows.append({'panel': 'hospital identity columns, repair F1', 'model': model, 'series': name, 'value': round(v, 3), 'ci_low': round(lo, 3), 'ci_high': round(hi, 3)})
            ax.bar(xs, vs, width=w, color=color, edgecolor='white', linewidth=0.5, zorder=2, label=name)
            ax.errorbar(xs, vs, yerr=[los, his], fmt='none', ecolor=INK2, elinewidth=0.5, capsize=1, zorder=3)
            for (x, v, h) in zip(xs, vs, his):
                ax.text(x, v + h + 0.02, f'{v:.2f}'[1:] if v < 1 else '1.0', ha='center', va='bottom', fontsize=5.6, color=INK)
        ax.axvline(n_open - 0.5, color=AXIS, linewidth=0.8, linestyle=(0, (3, 2)), zorder=1)
        ax.text((n_open - 1) / 2, 1.2, 'open-weight models (local)', ha='center', va='center', fontsize=6.4, color=MUTED)
        ax.text((n_open + len(models) - 1) / 2, 1.2, 'commercial models (API)', ha='center', va='center', fontsize=6.4, color=MUTED)
        ax.set_xticks(range(len(models)), [n for (_, n, _) in models])
        ax.set_xlim(-0.55, len(models) - 0.45)
        ax.set_ylim(0, 1.28)
        ax.set_yticks([0, 0.5, 1.0])
        ax.set_ylabel('Repair F1')
        ax.grid(axis='x', visible=False)
        ax.legend(loc='upper left', bbox_to_anchor=(1.0, 1.0), ncol=1, frameon=False, borderaxespad=0.3)
        fig.tight_layout(pad=0.3)
        save(fig, 'fig6_scale', rows)

def fig7() -> None:
    """Directed real-credit rewrites among known films; unchanged rates/CIs, explicit denominators."""
    from .scale import MODELS
    models = [m for m in MODELS if m[0] != 'local_olmo2-7b']
    n_open = sum((m[0].startswith('local_') for m in models))
    rows = []
    with plt.rc_context(SMALL):
        (fig, ax) = plt.subplots(figsize=(COL, 2.2))
        y = list(range(len(models)))[::-1]
        for (off, (prompt, label, color)) in zip((0.16, -0.16), (('standard', 'standard prompt', SERIES[0]), ('evidence', 'table-evidence prompt', SERIES[1]))):
            (vs, lo, hi) = ([], [], [])
            for (tag, model, _) in models:
                s_ = evidence_json(ARCHIVE / 'near' / f'{tag}__movies__summary.json')
                r = known_key_rates(ROOT / 'data/final/_near', 'movies', tag, s_)[f'real|1|{prompt}']
                vs.append(r['rate'])
                lo.append(r['ci'][0])
                hi.append(r['ci'][1])
                rows.append({'model': model, 'prompt': prompt, 'rate': r['rate'], 'ci_low': r['ci'][0], 'ci_high': r['ci'][1], 'films_known': r['entities']})
            yy = [v + off for v in y]
            ax.errorbar(vs, yy, xerr=[[v - l for (v, l) in zip(vs, lo)], [h - v for (v, h) in zip(vs, hi)]], fmt='none', ecolor=color, elinewidth=0.8, capsize=1.5, zorder=2)
            ax.scatter(vs, yy, s=14, color=color, edgecolor='white', linewidth=0.7, zorder=3, label=label)
            for (v, h, yi) in zip(vs, hi, yy):
                ax.text(max(h, v) + 0.02, yi, f'{v:.3f}', va='center', fontsize=5.8, color=INK)
        ax.axhline(len(models) - n_open - 0.5, color=AXIS, linewidth=0.8, linestyle=(0, (3, 2)), zorder=1)
        known = {r['model']: r['films_known'] for r in rows}
        ax.set_yticks(y, [f'{n} ({known[n]})' for (_, n, _) in models])
        ax.set_xlim(0, 1.18)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_ylim(-0.6, len(models) - 0.4)
        ax.set_xlabel('Director rewrites toward real-world credits')
        ax.grid(axis='y', visible=False)
        ax.tick_params(axis='y', length=0)
        ax.legend(loc='lower center', bbox_to_anchor=(0.32, 1.0), ncol=2, frameon=False, borderaxespad=0.2)
        fig.tight_layout(pad=0.3)
        save(fig, 'fig7_near_models', rows)

def fig0() -> None:
    """Controlled construction and the questions linking recovery, preservation and repair credit."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    fig = plt.figure(figsize=(7.1, 2.1))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 30)
    ax.axis('off')
    LINE = 2.05

    def box(x, y, w, h, title, lines, edge, face='white', size=6.3):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.2,rounding_size=0.8', linewidth=1.0, edgecolor=edge, facecolor=face))
        top = y + h
        ax.text(x + 0.9, top - 0.9, title, ha='left', va='top', fontsize=7.0, fontweight='bold', color=INK)
        for (k, line) in enumerate(lines):
            ax.text(x + 0.9, top - 3.6 - LINE * k, line, ha='left', va='top', fontsize=size, color=INK2)

    def arrow(x0, y0, x1, y1, dotted=False):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle='-|>', mutation_scale=7, linewidth=0.9, color=MUTED, shrinkA=0, shrinkB=0, linestyle=(0, (1, 2)) if dotted else 'solid'))
    box(0.6, 10.0, 16.4, 10.5, 'Benchmark table (O)', ['dirty + reference table', 'public, well-known entities', 'a city: $\\mathtt{birminghxm}$'], SERIES[0])
    conds = [('Fresh (F)', ['real records outside the benchmark', 'transferred errors: $\\mathtt{dxthan}$']), ('Words surrogate (W)', ['same rows and error cells', 'names from English words: $\\mathtt{xill\\ pine}$']), ('Syllable surrogate (S)', ['same rows and error cells', 'names from syllables: $\\mathtt{hepmxrmxr}$'])]
    ys = [21.2, 11.5, 1.8]
    for ((title, lines), y, color) in zip(conds, ys, SERIES[1:]):
        box(23.0, y, 25.0, 7.6, title, lines, color)
        arrow(17.2, 15.25, 22.8, y + 3.8)
    ax.text(10.0, 7.6, 'paired renaming or\nerror-recipe transfer', ha='center', va='center', fontsize=5.9, color=MUTED, linespacing=1.1)
    box(52.4, 7.6, 17.6, 15.3, 'Acceptance checks', ['error masks and recipes;', 'kinds, strength, formats;', 'names and leakage checks;', 'byte-identical rebuilds;', 'construction seed ranges'], AXIS)
    for y in ys:
        arrow(48.3, y + 3.8, 52.2, 15.25)
    box(74.4, 19.0, 25.0, 10.2, 'Recovery evidence', ['same method, prompt and information', 'four-condition contrasts', 'independent row-continuation probe'], AXIS)
    arrow(70.2, 18.5, 74.2, 22.5)
    box(74.4, 9.7, 25.0, 7.6, 'Assigned values', ['separate knowledge-conflict test', 'familiar facts vs table-value priority'], INK2, face=SURFACE)
    box(74.4, 0.3, 25.0, 7.6, 'Repair credit', ['separate Rayyan field checks', 'reference conversions vs external matches'], INK2, face=SURFACE)
    arrow(86.9, 18.8, 86.9, 17.5, dotted=True)
    arrow(86.9, 9.5, 86.9, 8.1, dotted=True)
    arrow(1.6, 3.8, 5.0, 3.8)
    ax.text(5.8, 3.8, 'table construction', va='center', fontsize=5.5, color=MUTED)
    arrow(1.6, 1.6, 5.0, 1.6, dotted=True)
    ax.text(5.8, 1.6, 'question sequence', va='center', fontsize=5.5, color=MUTED)
    save(fig, 'fig0_overview', [{'box': 'see src/figures.py fig0', 'note': 'diagram, no data'}])
if __name__ == '__main__':
    for f in (fig0, fig1, fig2, fig3, fig4, fig5, fig6, fig7):
        f()
        print(f.__name__, 'done')
