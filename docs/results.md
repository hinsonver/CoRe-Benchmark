# Result navigation

Read the current [paper PDF](../paper/latex/main.pdf) alongside [paper/result-map.json](../paper/result-map.json). That generated map binds all 25 displayed figures and tables to the current LaTeX labels and numbers. The labels below remain useful if numbering changes.

This candidate incorporates VE-M01–M05. [Revision provenance](../paper/revisions/README.md) connects the manuscript changes to the [source/PDF binding](../paper/revision-binding.json). Read the displays as a sequence of questions: what evidence enables recovery, which assigned values should remain, and which changes receive repair credit. These questions use separate comparisons rather than one shared experimental input.

Packaged products are in [results/tables](../results/tables/) and [results/figures](../results/figures/). A replay writes the corresponding `tables/`, `figures/` and `derived/` directories under its chosen output path. [Claim-to-evidence navigation](../paper/claim-map.md) explains what each result supports.

## Main-paper figures

| Stable label | Topic | Numerical source |
| --- | --- | --- |
| `fig:decomposition` | Four-condition repair scores | [fig1_decomposition.csv](../results/figures/fig1_decomposition.csv) |
| `fig:overview` | Error transfer and recovery evidence → assigned values → repair credit | [fig0_overview.csv](../results/figures/fig0_overview.csv) |
| `fig:year` | Movies year repairs after renaming | [fig2_year_range.csv](../results/figures/fig2_year_range.csv) |
| `fig:scale` | Full eight-model comparison, including Qwen2.5 scale | [fig6_scale.csv](../results/figures/fig6_scale.csv) |
| `fig:aligned` | Zero-shot and aligned Hospital/Movies scores | [fig3_aligned.csv](../results/figures/fig3_aligned.csv) |
| `fig:near` | Directed attribute rewrites and name restoration | [fig4_near_entity.csv](../results/figures/fig4_near_entity.csv) |
| `fig:nearmodels` | Director rewrites with two prompts | [fig7_near_models.csv](../results/figures/fig7_near_models.csv) |

## Main-paper tables

| Stable label | Topic | Source |
| --- | --- | --- |
| `tab:datasets` | Benchmark provenance and complementary diagnostic roles | [main.tex](../paper/latex/main.tex) |
| `tab:example` | Complete Hospital row across four conditions | [example.tex](../results/tables/example.tex) |
| `tab:conditions` | Interpretation of condition contrasts | [main.tex](../paper/latex/main.tex) |
| `tab:recoverability` | Recovery evidence categories | [main.tex](../paper/latex/main.tex) |
| `tab:construction` | Controlled-table sources and scale | [construction.tex](../results/tables/construction.tex) |
| `tab:movieserrors` | Movies error-transfer mechanisms | [movieserrors.tex](../results/tables/movieserrors.tex) |
| `tab:p1` | Saved continuation-probe results | [p1.tex](../results/tables/p1.tex) |
| `tab:main` | Identity-column repair and condition contrasts | [decomposition.tex](../results/tables/decomposition.tex) |
| `tab:detection` | Detection versus repair | [detection.tex](../results/tables/detection.tex) |
| `tab:counts` | Near-zero scores as repair counts | [counts.tex](../results/tables/counts.tex) |
| `tab:moviescols` | Movies results by column | [moviescols.tex](../results/tables/moviescols.tex) |
| `tab:beers` | Model-specific Beers boundary case | [beers.tex](../results/tables/beers.tex) |
| `tab:seeds` | Three construction-seed ranges | [seeds.tex](../results/tables/seeds.tex) |
| `tab:decoding` | Hospital syllable-name recovery categories | [decoding.tex](../results/tables/decoding.tex) |
| `tab:aligned` | Full twelve-row aligned/whole-table matrix | [aligned.tex](../results/tables/aligned.tex) |
| `tab:conflictexample` | Assigned Director value across name versions | [main.tex](../paper/latex/main.tex) |
| `tab:conflictcounts` | Known-film rewrite counts and controls | [conflictcounts.tex](../results/tables/conflictcounts.tex) |
| `tab:rayyan` | Population, sample, matches and field-check fractions | [rayyan_checks.tex](../results/tables/rayyan_checks.tex) |

## Extended products

The [extended-results companion](../paper/companions/06-扩展图表与结果明细.md) retains the full acceptance checks, conflict detail, original Rayyan counts and plot. The Rayyan plot uses [fig5_rayyan.csv](../results/figures/fig5_rayyan.csv) and [fig5_rayyan_display.csv](../results/figures/fig5_rayyan_display.csv); it is not an eighth main-paper figure. The two CSVs describe the same audit, not independent samples.

The current replay includes 19 table files, more than the eighteen displayed tables because several main-paper tables are inline and some generated views are retained only for extended inspection. In particular, [whole_table.tex](../results/tables/whole_table.tex) is an unused compact projection: use `tab:aligned` for the main-paper comparison. The full eight-model scale plot is the current main-paper view.

The overview's CSV is a diagram witness, not a set of experimental observations. Its current generator is [code/src/figures.py](../code/src/figures.py); the packaged figure is [fig0_overview.pdf](../results/figures/fig0_overview.pdf). The solid arrows show construction, and the dotted arrows indicate question order, not a data dependency between C1–C3.
