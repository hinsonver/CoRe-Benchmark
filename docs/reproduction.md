# Reproduction and scoring

Activate the [replay environment](../README.md#quick-start) and choose a new output directory:

```sh
python tools/core.py verify
python tools/core.py reproduce --output build/replayed
python tools/check_screening.py
python tools/check_rayyan.py
python supplements/beers-f-input-provenance/verify.py
```

These commands work offline after dependency installation. Current presentation writes19 table sources and nine numerical figure CSVs. To regenerate the15 original-format tables instead, use:

```sh
python tools/core.py reproduce --presentation frozen --output build/replayed-frozen
```

The choice changes presentation, not estimates. [Result navigation](results.md) maps the25 main-paper floats to code and assets; [revision provenance](../paper/revisions/README.md) records VE-M01–M05. Plot rendering may vary with fonts; the table bodies and CSVs are the numerical comparison targets.

| Entry | Executable scope |
| --- | --- |
| `tools/core.py verify` | Exact member hashes, both numerical-witness schemas/source bindings, anonymous known denominators and Rayyan counts; does not approve publication |
| `tools/core.py reproduce` | Statistical summaries, condition contrasts, block-bootstrap intervals, significance, seed/scale summaries and conflict rates, using included records or explicit numerical witnesses |
| `tools/core.py validate-private` | Requires all427 external original/scorer members and a truthful local-use record; regenerates both witness layers with original code, checks actual Rayyan scoring, then replays products; see [installation](data.md#validate-archived-replies) |
| `tools/check_screening.py` | All27 summary/screening groups, including anonymous known/entity flags for withheld replies; missing dependencies cannot silently use all targets |
| `tools/check_rayyan.py` | Anonymous actual-input cell recount plus independent saved audit bootstrap/114 scalar checks; public mode does not re-score the external raw TabClean table |
| `supplements/beers-f-input-provenance/verify.py` |150 archived response witnesses and the15-block historical/final-input disposition |

Public Rayyan recount yields808 error cells,498 edits,497 detected errors and461 credited repairs;434 of the repairs reproduce the date conversion. The independent title-matched field audit retains95.2% weighted reference-check failure (95% interval91.2–97.8%) using the948-cell type composition. It does not recover missing candidate responses or independently rejudge all encoding metadata.

[Release scope](release-scope.md) and the witness coverage map distinguish original-score regeneration from statistical replay. Of2,300 new P2 blocks,2,150 have row mappings and identical raw-rejudged counts;150 early Hospital non-spread blocks lack saved row mappings and retain archived counts only. P1 uses saved summaries and E4/E5 are not comprehensively re-scored. New model execution would be a new experiment, not recovery of these frozen results. No replay command calls a model or PubMed.

The original experiment modules remain source evidence, not a request to execute live services. Prompts, budgets and exclusions are described in the [run/scoring companion](../paper/companions/02-运行与评分规格.md); [limitations](limitations.md) gives the remaining boundaries.
