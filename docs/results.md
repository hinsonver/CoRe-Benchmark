# Result navigation

Read the current [paper PDF](../paper/latex/main.pdf) alongside [paper/result-map.json](../paper/result-map.json). That generated map binds all 25 displayed figures and tables to the current LaTeX labels and numbers. The labels below remain useful if numbering changes.

This is the current 2026-10-26 manuscript with the formal seven-section [technical report](../paper/CoRe-Supplementary-Technical-Report.pdf). [Revision provenance](../paper/revisions/README.md) separates historical records from the current [source/PDF binding](../paper/revision-binding.json). Read the displays as a sequence of questions: what evidence enables recovery, which assigned values should remain, and which changes receive repair credit. These questions use separate inputs and measurements.

Packaged products are in [results/tables](../results/tables/) and [results/figures](../results/figures/). A replay writes the corresponding `tables/`, `figures/` and `derived/` directories under its chosen output path. [Claim-to-evidence navigation](../paper/claim-map.md) explains what each result supports.

## Main-paper figures

| Stable label | Topic | Numerical source |
| --- | --- | --- |
| `fig:decomposition` | Missing identifier mappings versus retained year candidates | [fig1_recovery_evidence.csv](../results/figures/fig1_recovery_evidence.csv) |
| `fig:overview` | Three worked examples: recovery evidence → assigned values → repair credit | [fig0_overview.csv](../results/figures/fig0_overview.csv) |
| `fig:example` | Hospital city-error transfer in paired names and a fresh record | [fig_example_transfer.csv](../results/figures/fig_example_transfer.csv) |
| `fig:year` | Movies year repairs after renaming | [fig2_year_range.csv](../results/figures/fig2_year_range.csv) |
| `fig:scale` | Full eight-model comparison, including Qwen2.5 scale | [fig6_scale.csv](../results/figures/fig6_scale.csv) |
| `fig:aligned` | Zero-shot and aligned Hospital/Movies scores | [fig3_aligned.csv](../results/figures/fig3_aligned.csv) |
| `fig:near` | Directed attribute rewrites and name restoration | [fig4_near_entity.csv](../results/figures/fig4_near_entity.csv) |
| `fig:nearmodels` | Director rewrites with two prompts | [fig7_near_models.csv](../results/figures/fig7_near_models.csv) |

## Main-paper tables

| Stable label | Topic | Source |
| --- | --- | --- |
| `tab:datasets` | Benchmark provenance and complementary diagnostic roles | [main.tex](../paper/latex/main.tex) |
| `tab:conditions` | Interpretation of condition contrasts | [main.tex](../paper/latex/main.tex) |
| `tab:recoverability` | Recovery evidence categories | [main.tex](../paper/latex/main.tex) |
| `tab:construction` | Controlled-table sources and scale | [construction.tex](../results/tables/construction.tex) |
| `tab:movieserrors` | Movies error-transfer mechanisms | [movieserrors.tex](../results/tables/movieserrors.tex) |
| `tab:p1` | Uniform full-table-screen continuation reanalysis | [p1.tex](../results/tables/p1.tex), [integer provenance](../results/derived/uniform-continuation-provenance.md) |
| `tab:main` | Identity-column repair and condition contrasts | [decomposition.tex](../results/tables/decomposition.tex) |
| `tab:detection` | Detection versus repair | [detection.tex](../results/tables/detection.tex) |
| `tab:counts` | Near-zero repair counts; separate eight-model Holm families by dataset | [counts.tex](../results/tables/counts.tex) |
| `tab:moviescols` | Movies results by column | [moviescols.tex](../results/tables/moviescols.tex) |
| `tab:beers` | Model-specific Beers boundary case | [beers.tex](../results/tables/beers.tex) |
| `tab:seeds` | Three construction-seed ranges | [seeds.tex](../results/tables/seeds.tex) |
| `tab:decoding` | Hospital syllable-name recovery categories | [decoding.tex](../results/tables/decoding.tex) |
| `tab:aligned` | Full twelve-row aligned/whole-table matrix | [aligned.tex](../results/tables/aligned.tex) |
| `tab:conflictexample` | Assigned Director value across name versions | [main.tex](../paper/latex/main.tex) |
| `tab:conflictcounts` | Known-film rewrite counts and controls | [conflictcounts.tex](../results/tables/conflictcounts.tex) |
| `tab:rayyan` | Population, sample, matches and field-check fractions | [rayyan_checks.tex](../results/tables/rayyan_checks.tex) |

## Extended products

The [extended-results companion](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-6) retains the original three-dataset [condition overview](../results/figures/fig1_decomposition.csv), [complete Hospital row](../results/tables/example.tex), full acceptance checks, conflict detail, and original Rayyan counts and plot. The Rayyan plot uses [fig5_rayyan.csv](../results/figures/fig5_rayyan.csv) and [fig5_rayyan_display.csv](../results/figures/fig5_rayyan_display.csv); it is an extended display. The two CSVs describe the same audit, not independent samples.

The current replay includes 19 table files, more than the seventeen displayed tables because several main-paper tables are inline and some generated views are retained for extended inspection. In particular, [whole_table.tex](../results/tables/whole_table.tex) is an unused compact projection: use `tab:aligned` for the main-paper comparison. The full eight-model scale plot is the current main-paper view. Aligned Baran whiskers retain the first run's chunk-bootstrap interval translated to the three-run mean; they are neither a confidence interval for that mean nor an interval over seeds. The exact CSV endpoints remain unchanged.

The overview and construction CSVs are diagram witnesses, not new experimental observations. Their generator is [example_diagrams.py](../code/src/example_diagrams.py), called by [figures.py](../code/src/figures.py). The first result figure uses [evidence_panels.py](../code/src/evidence_panels.py), which checks saved repair counts and year accuracies. Its CSV provenance paths point to repository files.

The [archived diagnostics](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-7) and [diagnostic entry](../tools/review_diagnostics.py) supplement this display map without changing the frozen main table, intervals or significance.
