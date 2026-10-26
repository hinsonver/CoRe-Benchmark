# Reproduction and scoring

Run commands from the repository root with the replay environment activated. The [README quick start](../README.md#quick-start) installs the required packages. Select a new output directory for each replay.

## Offline replay

The unified coverage command runs the routes below in separate offline child processes, compares current and original frozen displays, and writes manifest-bound JSON plus a readable report:

```sh
python tools/reproduce_all.py --output build/all-offline
```

Exit 2 means execution completed with the explicit historical limits in the report; exit 1 means an unexpected failure. For a verified external historical installation, add both `--historical-root /absolute/external/history` and `--authorization-record /absolute/local-use.json`. No raw Movies file is copied into the core. The [coverage matrix](../REPRODUCTION.json) inventories all eleven experiment and supporting-evidence families.

The core and exact historical ZIPs are separate assets of the [same private GitHub prerelease](github-delivery.md). Follow that guide for authenticated acquisition and checksum verification, then the [data guide](data.md) for external installation and your own truthful local-use record. Private hosting does not establish reviewer access or remove any historical evidence limit below.

The original display-only commands remain unchanged:

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

The [result guide](results.md) distinguishes current main-paper displays from retained extended views. Current presentation adopts the [uniform continuation reanalysis and exact Beers Holm probabilities](../results/derived/uniform-continuation-provenance.md); frozen presentation retains all original table bytes. Other estimates and eleven CSVs are unchanged. The overview uses three independent examples of recovery, assigned values and repair credit; the Hospital example separates paired renaming from a fresh record. [Revision provenance](../paper/revisions/README.md) identifies the adopted manuscript. Diagram cells are author-selected illustration inputs, not a new experimental sample or a replacement for a full Movies table.

## What each scoring route checks

| Entry | Executable scope |
| --- | --- |
| `tools/reproduce_all.py` | Coordinates all offline checks, original execution plans, current 19-table/11-CSV and frozen 15-table byte comparisons. Reports technical completion, raw agreement, historical completeness and access separately. |
| `tools/score_continuations.py` | Independently parses saved replies, rebuilds sample rows and rejudges continuation summaries. Includes 144 archives by default and 24 additional Movies archives with exact external history. Current-versus-early scoring discrepancies are retained. |
| `tools/score_baselines.py` | Re-scores actual TabClean final tables, saved whole-table corrections and aligned replies/corrections, including development/label exclusions, means and intervals. Twelve absent correction lists and one unselected legacy metadata exception remain explicit. |
| `tools/core.py reproduce` | Recomputes condition contrasts, block-bootstrap intervals, significance checks, seed/scale summaries and conflict statistics from included evidence. Movies uses hash-bound numerical witnesses. Current continuation display derives maxima and pooled leakage from the separately bound uniform integer reanalysis; Beers uses exact sign-test probabilities before Holm. |
| `tools/core.py validate-private` | With the exact external historical archive installed and a truthful local-use record, re-scores archived Movies cleaning, aligned and nine-model conflict replies and compares their projections with the witnesses. [Installation and record requirements](data.md#validate-archived-replies). |
| `tools/check_rayyan.py` | Checks the retained field-audit evidence, weighted estimate and interval, and re-scores the archived TabClean output against its actual input version after excluding 150 development rows. |
| `tools/check_screening.py` | Checks the bound historical screening dependencies and known-entity subsets. Public Movies checks use anonymous saved flags; the historical route uses the exact original screening files. It does not issue new factual queries. |
| `tools/review_diagnostics.py` | Recomputes the portions of the archived sensitivity checks supported by included tables, block-count witnesses and saved matches. Reports aggregate-only output-pattern and historical-usage checks separately; does not re-judge omitted Movies replies or reconstruct a billing log. |
| `supplements/beers-f-input-provenance/verify.py` | Checks the historical/final Beers F input mapping and archived response witnesses, including 150 witnesses and the disposition of 15 input mismatches. |

The Rayyan scoring check yields 808 error cells, 498 effective edits and 461 credited repairs, of which 434 reproduce the reference date transformation. The field audit retains a 95.2% weighted reference-check failure estimate (95% interval 91.2–97.8%) conditional on saved title matches and checks, using the 948-cell type composition. It includes 114 scalar field rechecks; it does not reconstruct the full candidate retrieval responses or all encoding checks from raw external records.

The [archived-sensitivity section](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-7) gives the passing Hospital seeds, GLM incomplete-reply exclusions, rating-count edit categories, title-match coverage, exact cleaning prompt and scoped token totals. The [scoring specification](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-2) distinguishes the 40-difference bootstrap family from the separate eight-model sign-test families by dataset. The original 184-source SHA index records author-side audit provenance, not a claim that every source is redistributed here.

## Source code and experiment specification

[code/src/pipeline.py](../code/src/pipeline.py) and the other archived experiment modules record the original execution path. They are source evidence for the frozen study, not a requirement to run new model queries. [Run and scoring specification](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-2) gives models, prompts, budgets, scoring groups and exclusions; [construction and acceptance](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-1) explains the controlled tables.

The [execution planner](experiment-execution.md) provides the retained functions, exact frozen inputs, dependency preflight and explicitly gated single-run adapters. Its default is a read-only plan; it does not call the disabled historical pipeline shortcut. Fresh hosted runs use the reviewer's own key, account and quota. Offline configuration checks, optional model-catalogue lookup and exact-identifier confirmation are separate; neither a working key nor an advertised name certifies historical checkpoint equivalence. An author's former account access failure is not a model-wide availability test. Actual execution uses a separate environment and creates new outputs rather than recovering old ones. The accepted-sample Rayyan route likewise makes new requests only after explicit execution/network gates. This assembly performs no new model runs or PubMed queries. [Limitations](limitations.md) distinguishes these routes from exact historical reconstruction.
