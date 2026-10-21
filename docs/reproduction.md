# Reproduction and scoring

Run commands from the repository root with the replay environment activated. The [README quick start](../README.md#quick-start) installs the required packages. Select a new output directory for each replay.

## Offline replay

```sh
python tools/core.py verify
python tools/core.py reproduce --output build/replayed
python tools/check_rayyan.py
python supplements/beers-f-input-provenance/verify.py
```

`verify` checks the frozen evidence and its bindings. `reproduce` regenerates the statistical summaries, table sources and figure inputs without contacting models or retrieving new records. Its current presentation writes 19 table sources (17 full sources and two compact views) and nine unchanged CSVs for eight plot source groups. Plot rendering may vary with fonts; the numerical CSVs and table bodies are the comparison targets.

To select the original frozen formatting, use another output directory:

```sh
python tools/core.py reproduce \
  --presentation frozen \
  --output build/replayed-frozen
```

The [result guide](results.md) distinguishes current main-paper displays from retained extended views. The presentation choice changes layout and navigation, not the frozen estimates. Current sources include the VE-M04 overview: construction arrows connect the four conditions, while dotted arrows link the diagnostic questions. The conflict and Rayyan checks use their own inputs. [Revision provenance](../paper/revisions/README.md) records the manuscript changes through VE-M05.

## What each scoring route checks

| Entry | Executable scope |
| --- | --- |
| `tools/core.py reproduce` | Recomputes condition contrasts, block-bootstrap intervals, significance checks, seed/scale summaries and conflict statistics from included evidence. Movies uses hash-bound numerical witnesses. P1 is a saved-summary projection. |
| `tools/core.py validate-private` | With the exact external historical archive installed and a truthful local-use record, re-scores archived Movies P2, aligned and nine-model conflict replies and compares their projections with the witnesses. [Installation and record requirements](data.md#validate-archived-replies). |
| `tools/check_rayyan.py` | Checks the retained field-audit evidence, weighted estimate and interval, and re-scores the archived TabClean output against its actual input version after excluding 150 development rows. |
| `tools/check_screening.py` | Checks the bound historical screening dependencies and known-entity subsets. Public Movies checks use anonymous saved flags; the historical route uses the exact original screening files. It does not issue new factual queries. |
| `supplements/beers-f-input-provenance/verify.py` | Checks the historical/final Beers F input mapping and archived response witnesses, including 150 witnesses and the disposition of 15 input mismatches. |

The Rayyan scoring check yields 808 error cells, 498 effective edits and 461 credited repairs, of which 434 reproduce the reference date transformation. The field audit retains a 95.2% weighted reference-check failure estimate (95% interval 91.2–97.8%) conditional on saved title matches and checks, using the 948-cell type composition. It includes 114 scalar field rechecks; it does not reconstruct the full candidate retrieval responses or all encoding checks from raw external records.

## Source code and experiment specification

[code/src/pipeline.py](../code/src/pipeline.py) and the other archived experiment modules record the original execution path. They are source evidence for the frozen study, not a requirement to run new model queries. [Run and scoring specification](../paper/companions/02-运行与评分规格.md) gives models, prompts, budgets, scoring groups and exclusions; [construction and acceptance](../paper/companions/01-构造与验收细则.md) explains the controlled tables.

The replay environment supports the documented offline commands. Recreating live model execution would require its original external services and environment and would be a new run, with potentially different replies. This assembly performs no new model runs or PubMed queries. The remaining replay boundaries are collected in [limitations](limitations.md).
