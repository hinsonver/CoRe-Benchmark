# CoRe manuscript verification guide

This guide maps the adopted manuscript to the numerical replay and optional historical-validation entries in this private working revision. Section/table labels are LaTeX labels; [the result map](../result-map.json) supplies their current compiled numbers.

Earlier archives retain their original membership, displays and hashes, including the [fixed private release](https://github.com/hinsonver/CoRe-Benchmark/releases/tag/v0.1.0-a04-review-private-20261022). This repository revision adds the adopted paper, its current presentation sources and archived diagnostics without replacing those archives. The first figure selects saved Movies counts to contrast identifier mappings with retained year candidates; the original three-dataset overview and intervals remain in the extended displays.

## Public offline entry

Use `environment/requirements-replay.txt`. From the repository root, with a new output path:

```sh
python3 tools/core.py verify
python3 tools/core.py reproduce --output build/replayed
python3 tools/review_diagnostics.py
python3 tools/check_rayyan.py
```

The `scripts/verify.sh` and `scripts/reproduce.sh` wrappers use the selected `PYTHON` interpreter. Numerical replay requires no GPU, model key or network after dependency installation. Adding `--presentation frozen` selects the original table formatting. Current replay writes 19 table sources and eleven CSV files, retaining extended views as well as the eight main-paper figures. Inline explanatory tables and diagram cells are not additional experimental results.

## Manuscript to evidence map

All package paths below are relative to its extracted root. Generated paths are relative to the requested output directory.

| Analysis and manuscript labels | Public evidence | Entry | Replayed products |
| --- | --- | --- | --- |
| C1: `sec:knowledge`, `sec:memorization`, `sec:generalize`; `tab:main`, `tab:p1`, `tab:seeds`, `tab:aligned`, `tab:moviescols`; `fig:decomposition`, `fig:year`, `fig:scale`, `fig:aligned` | Archived block counts, construction and continuation summaries; `data/witnesses/movies.json`; original evidence under `artifacts/raw_outputs/p2/`, `p1/`, `aligned/`, `e4/`, `e5/` | `scripts/reproduce.sh` or `tools/core.py reproduce` | Contrasts, block-bootstrap intervals, significance, seed/scale summaries, aligned results and figure CSVs. Movies continuation uses saved summaries. |
| C2: `sec:conflict`, `tab:conflictcounts`, `fig:near`, `fig:nearmodels` | Anonymous movie entity IDs, per-model known flags and directed/any-edit indicators; Hospital/Beers archived conflict results | `tools/core.py verify` and public reproduce | Full/known entity-bootstrap checks, `tables/near.tex`, `conflictcounts.tex`, `fig4_near_entity.csv`, `fig7_near_models.csv`; retains known denominators and control edits. |
| C3: `sec:quality`, `sec:rayyan-audit`, `sec:rayyan-rewards`, `tab:rayyan` | Saved title matches and field checks, `data/manifests/RAYYAN_REPLAY.json`, `results/derived/rayyan_audit.json`, `data/provenance/rayyan/`, audit and actual TabClean inputs, development indices and archived output | `tools/check_rayyan.py`; public reproduce also invokes it | Weighted check-failure estimate/interval, `derived/rayyan_replay.json`, `tables/rayyan.tex`, Rayyan CSVs and the 808/498/461/434 scoring counts. |

Movie witnesses contain numerical projections, not row-level movie values or replies. `CORE_WITNESSES.json` binds projections and `CORE_SOURCES.json` records historical local-validation dependencies. Rayyan replay uses saved matches and scalar checks, with saved encoding outcomes, rather than a fresh PubMed retrieval. Beers F provenance has the additional entry `python3 supplements/beers-f-input-provenance/verify.py`.

## Current manuscript display projections

The current manuscript uses the full `tables/aligned.tex` matrix and full eight-model scale plot. `tables/rayyan_checks.tex` combines the original sampling counts with the five matched-cell check fractions. The unused six-row `tables/whole_table.tex` projection and original Rayyan count table/plot remain in [extended displays](06-扩展图表与结果明细.md). Figure `fig:aligned` and all its plotted intervals are unchanged.

The first figure's saved numerators are in `results/tables/moviescols.tex` and cross-checked against the year CSV. Its generator is [evidence_panels.py](../../code/src/evidence_panels.py). The overview and Hospital construction figure explain the protocol using existing examples; they add no experimental observations. Their generator is [example_diagrams.py](../../code/src/example_diagrams.py), called from `src/figures.py`. Packaged figure assets retain PDF, PNG, SVG and source-cell CSV exports. The complete Hospital identity-field table remains in the extended displays.

The checked table-display entry is [paper_presentation.py](../../code/src/paper_presentation.py). The normal `tools/core.py reproduce` entry applies it after statistical generation. It checks all 17 full source bodies, overlays captions and comparison grouping, and adds two compact sources. [Archived diagnostics](07-归档敏感性与输出核验.md) distinguish package-side recomputation from author-side raw-reply checks.

## Authorized historical movie validation

Readers supplying the exact historical inputs, replies and scoring code can use:

```sh
python3 tools/core.py validate-private \
  --private-root /external/historical-root \
  --authorization-record /external/rights-record.json \
  --output /new/historical-validation-results
```

The authorization record contains `purpose`, `rights_basis`, a `scope` with `historical_inputs` and `historical_outputs`, and `redistribution: false`. The entry checks 264 historical dependencies and 25 code files against the manifest before re-scoring saved direct-editing, aligned and conflict replies. Its witnesses must match the public witnesses. The continuation probe remains a saved-summary projection. New daily IMDb downloads or new model replies do not replace the historical materials.

## Local companion navigation and release metadata

The companion index is [README](README.md), with [construction](01-构造与验收细则.md), [runs/scoring](02-运行与评分规格.md), [Rayyan](03-Rayyan检索与评分材料说明.md), [adaptation](04-新基准应用指南.md), [extended displays](06-扩展图表与结果明细.md) and [archived diagnostics](07-归档敏感性与输出核验.md). This guide describes the current working revision, not a retroactive change to a fixed archive.

Author metadata is supplied in `CITATION.cff`. Public/reviewer access and publication approval remain separate: `verify --release` requires an external approval record bound to the final manifest. This private synchronization does not create public access.
