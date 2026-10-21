# Beers F archived input provenance supplement

This additive supplement resolves the input version used by three archived Beers F runs:
Qwen2.5-7B, Llama-3.1-8B and Qwen2.5-32B-AWQ. It does not replace any frozen table,
response, count, confidence interval, significance result or paper score.

## Replay

Run `python3 -I -S verify.py` from any directory. Python 3.11 or later and only its
standard library are required. No model, network, API key or original project is used.
The verifier checks file hashes, 150 response witnesses against reconstructed request
keys, every chunk count, and nine group summaries. It also reproduces the exact 15
discrepancies obtained by incorrectly scoring these replies against the final input.

## Which input belongs to which result

`run-input-map.json` binds exactly three unchanged run files, by SHA-256, to
`inputs/historical/`. This is the pre-location-fix table preserved in the experiment's
`data/raw/_fresh_v2/beers_fresh/`. Use it to replay these archived scores. Do not apply
this binding to other runs or overwrite `data/final/beers_fresh/` in the main artifact.
The default final input is included here under `inputs/final/` for comparison only.

The two versions differ in 122 dirty and 122 reference cells (107 states and 15 cities),
covering nine breweries; their 565 error positions are identical. Changed no-op decisions
on otherwise correct cells explain all 15 count differences. Error, detection and repair
counts do not change. All 150 historical prompt keys match the saved server response cache,
with exactly the same output text. The final input has only one unchanged prompt per run
in that saved cache. `audit.json` records per-cell explanations and source-cache line
numbers and hash; only the 150 relevant response witnesses are included, not a full cache.

## Interpretation and release integration

Keep the archived F scores as descriptive results from their actual historical input.
Beers knowledge contrasts use O/W/S; those results and C1–C3 are unchanged. The final-input
diagnostic scores in `audit.json` locate the discrepancy and are not replacement results.
This evidence does not establish a new response on the corrected final table.

For the public release, ship this directory beside the unchanged frozen artifact and link
this note and the replay command from its top-level README and reproduction documentation.
Raw-reply score validation for these three runs must use this hash-bound mapping rather
than the final-table default. Paper-product regeneration can continue to use the unchanged
archived counts. This supplement closes Beers F input provenance only; author metadata,
Movies licensing, GPT screening dependencies, Rayyan inputs/provenance and the remaining
public-release checks are separate gates. It is not a standalone complete CoRe release.

Original CoRe software/documentation follows the main artifact's MIT license. The historical
and final fresh-Beers inputs derive from the same recorded Wikidata CC0 source; both original
provenance JSON files are preserved. Response witnesses contain only the relevant archived
local-model outputs, with no credentials or unrelated cache entries.
