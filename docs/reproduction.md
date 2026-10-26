# Reproduction and scoring

Run commands from the repository root with the replay environment activated. The [README quick start](../README.md#quick-start) installs the required packages. Select a new output directory for each replay.

## Offline replay

```sh
python tools/core.py verify
python tools/core.py reproduce --output build/replayed
python tools/review_diagnostics.py
python tools/check_rayyan.py
python supplements/beers-f-input-provenance/verify.py
```

`verify` checks package membership and hash bindings. `reproduce` regenerates statistical summaries, table sources and figure inputs without contacting models or retrieving new records. Its current presentation writes 19 table sources (17 full sources and two compact views) and eleven CSVs. The two new CSVs carry the focused recovery comparison and Hospital construction example; the overview CSV now carries its worked examples. Figure rendering may vary with fonts and metadata; CSVs and table sources are the exact comparison targets.

To select the original frozen formatting, use another output directory:

```sh
python tools/core.py reproduce \
  --presentation frozen \
  --output build/replayed-frozen
```

The [result guide](results.md) distinguishes current main-paper displays from retained extended views. The presentation choice changes layout and navigation, not the frozen estimates. The overview uses three independent examples of recovery, assigned values and repair credit; the Hospital example separates paired renaming from a fresh record. [Revision provenance](../paper/revisions/README.md) identifies the adopted manuscript. Diagram cells are author-selected illustration inputs, not a new experimental sample or a replacement for a full Movies table.

## What each scoring route checks

| Entry | Executable scope |
| --- | --- |
| `tools/core.py reproduce` | Recomputes condition contrasts, block-bootstrap intervals, significance checks, seed/scale summaries and conflict statistics from included evidence. Movies uses hash-bound numerical witnesses. The continuation probe is a saved-summary projection. |
| `tools/core.py validate-private` | With the exact external historical archive installed and a truthful local-use record, re-scores archived Movies cleaning, aligned and nine-model conflict replies and compares their projections with the witnesses. [Installation and record requirements](data.md#validate-archived-replies). |
| `tools/check_rayyan.py` | Checks the retained field-audit evidence, weighted estimate and interval, and re-scores the archived TabClean output against its actual input version after excluding 150 development rows. |
| `tools/check_screening.py` | Checks the bound historical screening dependencies and known-entity subsets. Public Movies checks use anonymous saved flags; the historical route uses the exact original screening files. It does not issue new factual queries. |
| `tools/review_diagnostics.py` | Recomputes the portions of the archived sensitivity checks supported by included tables, block-count witnesses and saved matches. Reports aggregate-only output-pattern and historical-usage checks separately; does not re-judge omitted Movies replies or reconstruct a billing log. |
| `supplements/beers-f-input-provenance/verify.py` | Checks the historical/final Beers F input mapping and archived response witnesses, including 150 witnesses and the disposition of 15 input mismatches. |

The Rayyan scoring check yields 808 error cells, 498 effective edits and 461 credited repairs, of which 434 reproduce the reference date transformation. The field audit retains a 95.2% weighted reference-check failure estimate (95% interval 91.2–97.8%) conditional on saved title matches and checks, using the 948-cell type composition. It includes 114 scalar field rechecks; it does not reconstruct the full candidate retrieval responses or all encoding checks from raw external records.

The [archived-sensitivity section](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-7) gives the passing Hospital seeds, GLM incomplete-reply exclusions, rating-count edit categories, title-match coverage, exact cleaning prompt and scoped token totals. The [scoring specification](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-2) distinguishes the 40-difference bootstrap family from the separate eight-model sign-test families by dataset. The original 184-source SHA index records author-side audit provenance, not a claim that every source is redistributed here.

## Source code and experiment specification

[code/src/pipeline.py](../code/src/pipeline.py) and the other archived experiment modules record the original execution path. They are source evidence for the frozen study, not a requirement to run new model queries. [Run and scoring specification](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-2) gives models, prompts, budgets, scoring groups and exclusions; [construction and acceptance](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-1) explains the controlled tables.

The replay environment supports the documented offline commands. Recreating live model execution would require its original external services and environment and would be a new run, with potentially different replies. This assembly performs no new model runs or PubMed queries. The remaining replay boundaries are collected in [limitations](limitations.md).
