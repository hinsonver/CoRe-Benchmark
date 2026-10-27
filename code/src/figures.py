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

def f1_ci(chunks: list[dict], group: str, n: int=2000, *, model=None, condition=None) -> tuple[float, float, float]:
    """Repair F1 and its 95% bootstrap interval over chunks."""

    if os.environ.get('CORE_CLUSTER_RESULTS'):
        data=json.loads(Path(os.environ['CORE_CLUSTER_RESULTS']).read_text())
        base=next(d for d in ('hospital','movies','beers') if condition.startswith(d))
        cond='F' if '_fresh' in condition else 'W' if '_surrogatewords' in condition else 'S' if '_surrogate' in condition else 'O'
        record=data['score_intervals'][f'{model}|{base}|{cond}|{group}']
        value=round(record['point'],4)
        return (value,*record['ci']) if record['interval_available'] else (value,value,value)
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
                (v, lo, hi) = f1_ci(ch, group,model=MODEL,condition=cond)
                vals.append(v)
                errs.append((lo, hi))
                available=not os.environ.get('CORE_CLUSTER_RESULTS') or lo!=hi
                rows.append({'dataset': base, 'columns': group, 'condition': name, 'repair_f1': round(v, 3), 'ci_low': round(lo, 3) if available else None, 'ci_high': round(hi, 3) if available else None})
            display_order = [0, 2, 3, 1]
            x = [0, 1, 2, 3.6]
            shown_vals = [vals[i] for i in display_order]
            shown_errs = [errs[i] for i in display_order]
            ax.bar(x, shown_vals, width=0.72, color=[SERIES[i] for i in display_order], edgecolor='white', linewidth=0.8, zorder=2)
            eligible=[i for i,e in enumerate(shown_errs) if not os.environ.get('CORE_CLUSTER_RESULTS') or e[0]!=e[1]]
            ax.errorbar([x[i] for i in eligible],[shown_vals[i] for i in eligible], yerr=[[shown_vals[i]-shown_errs[i][0] for i in eligible],[shown_errs[i][1]-shown_vals[i] for i in eligible]], fmt='none', ecolor=INK2, elinewidth=0.6, capsize=1.2, zorder=3)
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

# Baran whiskers retain a translated first-run interval, not a confidence interval of the mean.
# The legacy ci_low/ci_high CSV columns hold those unchanged display endpoints.
def render_aligned_csv(source: Path, output_dir: Path):
    """Plot saved centers; only DeepSeek has corresponding bootstrap intervals."""
    with Path(source).open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    series = ["DeepSeek-V4-Pro, aligned", "Baran, aligned", "DeepSeek-V4-Pro, zero-shot"]
    expected = {(dataset, name, condition) for dataset in ("hospital", "movies")
                for name in series for condition in CONDITIONS}
    keys = [(row["dataset"], row["series"], row["condition"]) for row in rows]
    if len(keys) != 24 or set(keys) != expected:
        raise ValueError("expected exactly the 24 fixed aligned-result rows")
    with plt.rc_context(SMALL):
        fig, axes = plt.subplots(1, 2, figsize=(COL, 1.6), sharey=True)
        for ax, base, title in zip(axes, ("hospital", "movies"), ("Hospital", "Movies")):
            x = list(range(4))
            for name, color, mk in zip(series, (SERIES[0], SERIES[1], SERIES[2]), ("o", "s", "o")):
                selected = {(row["condition"]): row for row in rows
                            if row["dataset"] == base and row["series"] == name}
                vals = [selected[condition] for condition in CONDITIONS]
                v = [float(row["repair_f1"]) for row in vals]
                ax.plot(x, v, color=color, linewidth=1.4, marker=mk, markersize=3.6, markeredgecolor="white",
                        markeredgewidth=0.8, zorder=2, label=name)
                if name != "Baran, aligned":
                    eligible=[i for i,row in enumerate(vals) if row['ci_low']!='' and row['ci_high']!='']
                    ax.errorbar([x[i] for i in eligible],[v[i] for i in eligible],
                                yerr=[[v[i]-float(vals[i]['ci_low']) for i in eligible],
                                      [float(vals[i]['ci_high'])-v[i] for i in eligible]],
                                fmt="none", ecolor=color, elinewidth=0.6, capsize=1.2, zorder=2)
            ax.set_xticks(x, ["O", "F", "W", "S"])
            ax.set_xlim(-0.3, 3.3)
            ax.set_ylim(0, 1.05)
            ax.set_yticks([0, 0.5, 1.0])
            ax.set_title(title, loc="left", pad=3)
        axes[0].set_ylabel("Repair F1")
        h, l = axes[0].get_legend_handles_labels()
        fig.legend(h, l, loc="upper center", ncol=2, bbox_to_anchor=(0.54, 1.02), frameon=False)
        fig.tight_layout(pad=0.3, w_pad=0.6, rect=(0, 0, 1, 0.8))
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_output = output_dir / 'fig3_aligned.csv'
        if csv_output.resolve() != Path(source).resolve():
            csv_output.write_bytes(Path(source).read_bytes())
        for extension in ("pdf", "png"):
            fig.savefig(output_dir / f"fig3_aligned.{extension}", dpi=300,
                        bbox_inches="tight", pad_inches=0.02)
        return fig



def fig3() -> None:
    """Render the aligned comparison without re-scoring historical replies."""
    source = FIG / "fig3_aligned.csv"
    if not source.is_file():
        source = ROOT / "results" / "figures" / "fig3_aligned.csv"
    plt.close(render_aligned_csv(source, FIG))

def fig4() -> None:
    """Directed fact/name rewrites by DeepSeek-V4-Pro; one row per target, entity-bootstrap CIs."""
    items = [('movies', 'real|1', 'Film, other director'), ('movies', 'near|1', 'Film title, one letter off'), ('hospital', 'near|1', 'Hospital name, one letter off'), ('beers', 'near|1', 'Brewery name, one letter off'), ('beers', 'real|1', 'Brewery, other city'), ('hospital', 'real|1', 'Hospital, other city')]
    rows = []
    with plt.rc_context(SMALL):
        (fig, ax) = plt.subplots(figsize=(COL, 2.4))
        y = [6, 2, 1, 0, 5, 4]
        for (off, (prompt, label, color)) in zip((0.16, -0.16), (('standard', 'standard prompt', SERIES[0]), ('evidence', 'table-evidence prompt', SERIES[1]))):
            (vs, lo, hi, point_labels) = ([], [], [], [])
            for (ds, key, name) in items:
                summary = evidence_json(ARCHIVE / 'near' / f'{MODEL}__{ds}__summary.json')
                s_ = known_key_rates(ROOT / 'data/final/_near',ds,MODEL,summary) if os.environ.get('CORE_CLUSTER_RESULTS') else summary['key_rates']
                r = s_[f'{key}|{prompt}']
                vs.append(r['rate'])
                lo.append(r['ci'][0])
                hi.append(r['ci'][1])
                available=r.get('interval_available',True)
                point_labels.append(f"{r['rate']:.3f}" if available else f"{int(r['rewritten'])}/{r['entities']}")
                extra={'interval_kind':r['kind'],'rewritten_entities':r['rewritten']} if os.environ.get('CORE_CLUSTER_RESULTS') else {}
                rows.append({'item': name, 'prompt': prompt, 'rate': r['rate'], 'ci_low': r['ci'][0] if available else None, 'ci_high': r['ci'][1] if available else None, 'entities': r['entities'],**extra})
            yy = [v + off for v in y]
            eligible=[i for i in range(len(vs)) if not os.environ.get('CORE_CLUSTER_RESULTS') or lo[i]!=hi[i]]
            ax.errorbar([vs[i] for i in eligible],[yy[i] for i in eligible], xerr=[[vs[i]-lo[i] for i in eligible],[hi[i]-vs[i] for i in eligible]], fmt='none', ecolor=color, elinewidth=0.8, capsize=1.5, zorder=2)
            ax.scatter(vs, yy, s=14, color=color, edgecolor='white', linewidth=0.7, zorder=3, label=label)
            for (v, h, yi, text) in zip(vs, hi, yy,point_labels):
                ax.text(max(h, v) + 0.02, yi, text, va='center', fontsize=5.8, color=INK)
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
                (v, lo, hi) = f1_ci(chunks(tag, CONDS['hospital'][k]), 'identity',model=tag,condition=CONDS['hospital'][k])
                xs.append(i + (k - 1.5) * w)
                vs.append(v)
                los.append(v - lo)
                his.append(hi - v)
                available=not os.environ.get('CORE_CLUSTER_RESULTS') or lo!=hi
                rows.append({'panel': 'hospital identity columns, repair F1', 'model': model, 'series': name, 'value': round(v, 3), 'ci_low': round(lo, 3) if available else None, 'ci_high': round(hi, 3) if available else None})
            ax.bar(xs, vs, width=w, color=color, edgecolor='white', linewidth=0.5, zorder=2, label=name)
            eligible=[i for i in range(len(xs)) if not os.environ.get('CORE_CLUSTER_RESULTS') or los[i]+his[i]!=0]
            ax.errorbar([xs[i] for i in eligible],[vs[i] for i in eligible], yerr=[[los[i] for i in eligible],[his[i] for i in eligible]], fmt='none', ecolor=INK2, elinewidth=0.5, capsize=1, zorder=3)
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
            (vs, lo, hi, point_labels) = ([], [], [], [])
            for (tag, model, _) in models:
                s_ = evidence_json(ARCHIVE / 'near' / f'{tag}__movies__summary.json')
                r = known_key_rates(ROOT / 'data/final/_near', 'movies', tag, s_)[f'real|1|{prompt}']
                vs.append(r['rate'])
                lo.append(r['ci'][0])
                hi.append(r['ci'][1])
                available=r.get('interval_available',True)
                point_labels.append(f"{r['rate']:.3f}" if available else f"{int(r['rewritten'])}/{r['entities']}")
                extra={'interval_kind':r['kind'],'rewritten_entities':r['rewritten']} if os.environ.get('CORE_CLUSTER_RESULTS') else {}
                rows.append({'model': model, 'prompt': prompt, 'rate': r['rate'], 'ci_low': r['ci'][0] if available else None, 'ci_high': r['ci'][1] if available else None, 'films_known': r['entities'],**extra})
            yy = [v + off for v in y]
            eligible=[i for i in range(len(vs)) if not os.environ.get('CORE_CLUSTER_RESULTS') or lo[i]!=hi[i]]
            ax.errorbar([vs[i] for i in eligible],[yy[i] for i in eligible], xerr=[[vs[i]-lo[i] for i in eligible],[hi[i]-vs[i] for i in eligible]], fmt='none', ecolor=color, elinewidth=0.8, capsize=1.5, zorder=2)
            ax.scatter(vs, yy, s=14, color=color, edgecolor='white', linewidth=0.7, zorder=3, label=label)
            for (v, h, yi, text) in zip(vs, hi, yy,point_labels):
                ax.text(max(h, v) + 0.02, yi, text, va='center', fontsize=5.8, color=INK)
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
    """Author-selected manuscript illustration, not new experimental evidence."""
    from .example_diagrams import render_overview
    result = render_overview(FIG, SERIES)
    plt.close(result.figure)


def fig_example() -> None:
    """Construct the four illustrated Hospital cells from included tables."""
    from .example_diagrams import render_construction
    result = render_construction(FIG, SERIES)
    plt.close(result.figure)


def fig1_recovery() -> None:
    """Recompute plotted fractions from the saved column table and year counts."""
    from .evidence_panels import render_recovery_evidence
    result = render_recovery_evidence(FIG, SERIES)
    plt.close(result.figure)


if __name__ == '__main__':
    for f in (fig0, fig_example, fig1, fig2, fig1_recovery, fig3, fig4, fig5, fig6, fig7):
        f()
        print(f.__name__, 'done')
