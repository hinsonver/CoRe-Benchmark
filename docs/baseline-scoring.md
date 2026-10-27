# Offline re-scoring of saved baselines

This command reconstructs baseline counts and repair metrics from saved outputs. It does not invoke a model, retrain or rerun Baran/Raha, regenerate a table, query PubMed, or change an archived result. It complements the package's numerical-witness replay; numerical witnesses are never described as raw-output validation.

From the package root, using the environment documented in the package:

```sh
python tools/score_baselines.py --output build/raw-baselines
```

The output directory must be new and beneath this package's `build/`. Existing directories are rejected before replay starts. The command writes `baseline-scores.json` containing aggregate counts, metrics, per-run coverage, comparisons, and dependency hashes. It contains no table cells, saved model replies, correction values, or movie identifiers. Exit status `0` means all performed comparisons match; it does **not** mean all historical runs have raw outputs. Exit status `2` means the report retains differences for investigation, including historical unseeded row-metadata discrepancies described below. Missing files, invalid selected-run metadata, shape errors, altered source hashes, or authorization failures stop the command without an accepted report.

## What is independently reconstructed

| Family | Default-core raw coverage | Reconstruction and archive comparison |
|---|---:|---|
| TabClean | 9 conditions | Hospital and Beers O/F/W/S plus Rayyan: complete saved cleaned table, dirty/clean input pair, and full development sample |
| Whole-table Baran/Raha | 42 raw runs; 12 count-only runs | Saved cell fixes reconstructed into a table; original P2 scoring independently cross-checked; per-run counts/metrics and grouped mean/SD compared |
| Aligned correction | 40 raw archives | Hospital and Beers O/F/W/S: unseeded Baran, three fixed Baran runs, and saved DeepSeek replies/corrections; exact rows/labels, aggregate metrics, and paired bootstrap intervals checked |

TabClean's saved development rows must equal its seed-42 pandas sample in full values and order, not merely in sample size. All 150 development rows are excluded from both error and prediction denominators. Hospital/Beers TabClean inputs must equal the corresponding frozen condition tables. Rayyan deliberately uses its actual saved TabClean input version, not the separate audit version; the checked development-index provenance and frozen 808-error/498-prediction/497-detection/461-repair result are retained.

For aligned correction, the saved 20 distinct labels are excluded. Both surrogates reuse the original condition's labels; the fresh condition uses its own saved labels. The scorer regenerates the original entity-spread chunk membership and requires every saved chunk ID and remaining row list to match. Saved LLM fixes must also match parsing of the saved reply. As in the repair-only task, only erroneous cells in the displayed, nonlabelled rows count; changes to already-correct cells are outside that task's denominator. All three Baran F1s, their mean and the LLM F1 are recomputed. This historical score audit also reproduces the archived 2,000-draw interval against the first Baran run; that diagnostic is not the manuscript's interval. For the displayed DeepSeek cluster intervals and comparisons against the mean of the same three fixed Baran runs, use `tools/core.py reproduce` or `tools/replay_cluster_statistics.py`, as specified in the [statistical guide](cluster-inference.md). Baran mean points have no displayed interval.

Only pure functions and constants are extracted from `code/src/probe_clean.py` using the Python AST. Client imports, API configuration, environment files, generation commands, and training modules are not loaded. Case, whitespace and comma normalization, exact dirty-versus-clean error membership, prediction de-duplication/no-op behavior, four-decimal metric rounding, and grouped NumPy arithmetic follow the frozen scorer. In particular, NumPy's original runtime-summary rounding is preserved rather than converting to Python float before rounding.

## Explicit raw-output gap: 12 whole-table runs

These exact archived E5 runs have counts and metrics but did not save `fixes`:

```text
beers_orig__perfect__seed0.json
beers_orig__perfect__seed1.json
beers_orig__perfect__seed2.json
beers_orig__raha__seed0.json
beers_orig__raha__seed1.json
beers_orig__raha__seed2.json
hospital__perfect__seed0.json
hospital__perfect__seed1.json
hospital__perfect__seed2.json
hospital__raha__seed0.json
hospital__raha__seed1.json
hospital__raha__seed2.json
```

They remain `archived_count_only` with `raw_verified: false`. Recomputing arithmetic from their archived counts is not validation of the underlying corrections. Their count-based arithmetic still participates in the original grouped summary, with raw/count-only coverage reported separately. No corrections are invented; no archived scores are replaced. A focused author-side check of these exact filenames in the existing experiment result copies also found no `fixes` payload. Running Baran again would be a new run, not recovery of these historical raw outputs, and is not part of this command.

## Optional exact, locally authorized Movies history

The default statistical core excludes Movies row contents. The exact historical ZIP is a [separate Release asset in the same private GitHub repository](github-delivery.md); follow its authenticated download and checksum instructions and the [external installation guide](data.md). By default, Movies is explicitly `excluded_not_raw_verified`, and its numerical witnesses are not used as substitutes. To inspect exact already-saved history, the user must separately supply both a historical-root path and their own truthful local-use authorization record:

```sh
python tools/score_baselines.py \
  --output build/raw-baselines-authorized \
  --historical-root /external/exact-historical-root \
  --authorization-record /external/actual-local-use-record.json
```

The existing `core_runtime.preflight_private` contract validates all 264 private dependency hashes in `CORE_SOURCES.json`, requires a nonempty actual `purpose` and `rights_basis`, requires `historical_inputs` and `historical_outputs` in `scope`, and requires `redistribution: false`. This validates the recorded declaration and exact bytes; it is not a legal ruling or a grant of rights. An author-side declaration is not proof of a reader's rights. The historical tree must be external to the core package. The command neither installs that history nor copies its row contents into outputs.

With complete authorized history, this adds the four Movies TabClean conditions, 30 whole-table baseline runs, and 20 aligned raw archives (the two additional aligned files are labels and comparison metadata). The 12 existing default-core count-only runs remain count-only. The optional path is only for offline evaluation of exact existing history, not new model/API calls or publication.

### Retained historical unseeded Movies-fresh metadata mismatch

The exact historical `aligned/baran__movies_fresh.json` is an unseeded earlier diagnostic: 19 of its 50 saved chunk row lists differ from the current bound label exclusions; it includes 12 currently labelled rows and excludes 12 other rows instead. Its 20 excluded rows match the author-side earlier `_fresh_v2/labels_movies.json`, not the current bound fresh labels. That earlier file is not imported into this package or substituted for current labels.

The report preserves the source and marks this archive `historical_row_metadata_mismatch`, with `raw_verified: false`. It reconstructs aggregate counts over its own saved rows only, reports scalar mismatch counts, and does not call these counts current-label validation. This leaves 59 of the 60 inspected authorized aligned archives fully validated, not 60. The command emits the report with exit status `2`; the mismatch is never silently normalized away.

The three current seeded Movies-fresh archives and the saved LLM archive match current labels. They determine the frozen comparison. The complete `baran__` consumer check found the same selection rule in `aligned.compare`, `paper_tables.aligned_table`, `paper_tables_frozen.aligned_table`, and `figures.fig3`: existing `__run*.json` files take precedence, with the unseeded file used only as a fallback. The three bound seeded files exist for every condition. The result-map's aligned artifacts are `fig:aligned` (Figure 6, `figures.py`) and `tab:aligned` (Table 13, `paper_tables.py` with presentation formatting); neither selects the stale unseeded archive. Their selected-run comparison differences are separately reported. The report includes hashes of these selection-source modules for this disposition; it does not alter any frozen result or revoke the mismatch status.

## Tests and interpretation

```sh
python -m unittest discover -s tests -p test_baseline_scoring.py
```

The tests cover normalization/no-ops, exact error membership, development exclusions and full-sample equality, incorrect table shape, ragged CSVs, invalid fix positions, changed metadata, honest missing-fix status, preserved discrepancies, original NumPy rounding, label-source reuse, exact aligned rows/chunk IDs, reply/fix consistency, missing and changed hash-bound inputs, paired authorization flags, payload exclusion, refusal to overwrite outputs, explicit legacy-unseeded mismatch reporting, and continued fail-closed behavior for selected seeded-row mismatches.

The default-core route checks 9 TabClean conditions, 42 correction-list whole-table runs, 12 count-only runs and 40 aligned archives. The authorized route checks all 264 exact private dependencies during preflight and binds 254 actually consumed baseline dependencies; its coverage is 13 TabClean conditions, 72 correction-list whole-table runs, the same 12 count-only runs and 59 fully validated aligned archives out of 60 inspected. The unseeded metadata exception remains separate from the 36 selected aligned group comparisons. Run `tools/reproduce_all.py` to create a fresh `baselines/baseline-scores.json` alongside a manifest-bound `coverage.json`, identifying the exact source used. The historical route's expected exit status is `2`, not an unqualified all-archive pass. Neither mode recovers missing correction lists or independently establishes reviewer access or submission eligibility.
