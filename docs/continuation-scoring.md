# Offline rejudgment of row-continuation replies

This entry point starts with saved **trial output text**, original clean/dirty CSV
inputs, and the archived sampling configuration. It does not project saved summary
statistics, regenerate replies, load model clients, or contact a service.

```sh
python tools/score_continuations.py --output build/raw-continuations
```

The default covers all 144 included non-Movies archives (8,200 trials): 29 each
for Beers, Flights, Hospital and Tax, and 28 for Rayyan. Movies is **not** inferred
from the public numerical witness. Its 24 original archives (1,400 trials) require
an external, exact historical installation and an explicit local-use record:

```sh
python tools/score_continuations.py \
  --output build/raw-continuations-with-history \
  --historical-root /path/to/external/history \
  --authorization-record /path/to/local-use.json
```

The two historical arguments must be supplied together. The existing
`core_runtime.preflight_private` contract checks purpose, rights basis, scope for
historical inputs and outputs, and `redistribution: false`, then verifies all
264 SHA-bound private dependencies. The historical probe and data-helper source
hashes are also verified. The record documents the user's stated local-use basis;
it does not establish a legal right or authorize redistribution. Missing inputs,
wrong hashes, symlinks, incomplete trial sequences and unavailable authorizations
fail closed. No numerical-witness or saved-summary fallback is available.

## What is reconstructed

Only the frozen `parse_row`, `structural_baselines`, `_top`,
`structural_guesses`, and `counter_columns` function definitions are extracted
and compiled from their ASTs. Neither module's imports, table loader, `run()`,
`main()`, nor `src.clients` is executed. The row-continuation source SHA is
`cb800c53af433954a3e22d198184fecb4c2448dda269a9af4f1fc4da2043ed87`.
The optional historical mode extracts the historical counter helper from its
separately bound source, not the adapted public table loader.

All cells are loaded as strings with empty strings preserved. Dirty headers are
aligned positionally to clean headers. Tax uses only its original first 5,000
rows; other table shapes are Beers 2,410×11, Flights 2,376×7, Hospital 1,000×20,
Rayyan 1,000×11, and Movies 7,390×17. Sampling is exactly
`Random(seed).sample(pool, min(max(n, 100), len(pool)))[:n]`, with the optional
error-row filter applied first. Every saved row index must match that sequence.

The parser uses only the first nonblank line after the frozen backtick stripping,
and accepts it only at the original column count. Explicit failed-call trials
are not parsed. Failed and unparseable trials remain in the parse/exact-row
denominator, but contribute no cell-scoring denominators. Row-counter columns
are excluded from cell scoring, not from exact-row equality.

For parseable trials, the tool recomputes inferable, noninferable, hard, clean-value
leakage and hard-leakage numerators/denominators and rates, plus every noninferable
per-column model/mode/transition/structural statistic. The structural screen uses
full-table mode, successor counts, admitted functional dependencies and previous-value
±1 guesses. Queried target votes are subtracted; this is not strict full-row refitting.
Dataset/source baseline counts are cached without changing iteration
or tie-breaking order. Saved `parsed` flags and all archived summary fields are
compared independently. A legacy omission of `failed_calls` is reported explicitly,
not silently filled into the original archive.

## Outputs and exit status

Only a **new** output directory is permitted. Package-local output must be below
`build/`; output overlapping any supplied historical root is rejected. Sources
are read-only and no historical file is copied into the statistical core.

- `continuation-scores.json`: reconstructed summaries, aggregate counters,
  mismatch field paths, legacy schema omissions, sampling/parsed-flag checks,
  source SHA bindings and historical-authorization hash.
- `continuation-scores.csv`: one numerical summary row per archive.

Neither file contains raw trial replies, prompts, cell values, row-level records
or mismatch values. Historical Movies column names are replaced by positional
labels, and per-column mismatch paths are redacted. The full unredacted summary
is compared in memory before this presentation redaction.

Exit status is **1** if any archived summary value or parsed flag differs,
even after every archive was successfully scored and the reports were written.
A zero exit status means the compared values agree; a reported legacy missing
field remains a schema difference. Invalid inputs raise an error before the
output directory is created. A nonzero discrepancy result must not be described
as an all-pass frozen-summary reproduction.

## Observed archived scoring-convention difference (2026-10-26)

The complete author-local validation rejudged all **168 archives / 9,600 trials**.
All sampling sequences and saved parsed flags agree. There are five saved failed
calls and 511 unparseable replies (368 in the included non-Movies subset).
Twenty-four legacy summaries omit `failed_calls` (20 included, four Movies).
Of 13,524 archived summary leaves compared, **253 differ in 12 archives**; the
other 156 archives match their saved summary values.

The 12 differing archives all have this historical filename pattern:

`artifacts/raw_outputs/p1/custom_deepseek_deepseek-v4-pro__{dataset}__{source}__anon.json`

where `dataset` is each of `beers`, `flights`, `hospital`, `rayyan`, `tax`,
`movies_1`, and `source` is each of `clean`, `dirty`. These are the original
DeepSeek 100-trial runs, not the named or error-row 50-trial archives.

| Dataset/source | Archived hard cells → reconstructed | Archived hard accuracy → reconstructed | Archived hard-leak cells → reconstructed |
|---|---:|---:|---:|
| Beers clean | 201 → 375 | 0.0647 → 0.0800 | 0 → 0 |
| Beers dirty | 239 → 417 | 0.0502 → 0.0695 | 29 → 31 |
| Flights clean | 139 → 149 | 0 → 0 | 0 → 0 |
| Flights dirty | 192 → 228 | 0 → 0 | 44 → 49 |
| Hospital clean | 126 → 144 | 0.0238 → 0.0208 | 0 → 0 |
| Hospital dirty | 167 → 200 | 0.0599 → 0.0700 | 1 → 1 |
| Rayyan clean | 238 → 736 | 0 → 0 | 0 → 0 |
| Rayyan dirty | 241 → 738 | 0 → 0 | 56 → 91 |
| Tax clean | 475 → 887 | 0 → 0 | 0 → 0 |
| Tax dirty | 469 → 874 | 0 → 0 | 18 → 30 |
| Movies clean | 466 → 1,271 | 0.0064 → 0.0024 | 0 → 0 |
| Movies dirty | 490 → 1,362 | 0.0041 → 0.0059 | 32 → 100 |

Affected fields are `hard_cells`, some `acc_hard`, some `leak_hard_cells`/
`leak_hard_rate`, and per-column `freq`, `trans` or `structural` statistics.
Parsing, exact-row matches, inferable/noninferable counts and rates, and total
leakage counts/rates do not differ.

A read-only diagnostic reproduced **every archived field of all 12** by applying
two changes to the frozen helper behavior: ignore `_top`'s exclusion argument
(non-leave-one-out fitting), and omit the arithmetic ±1 structural guesses.
Ignoring exclusion alone explains most differences, but leaves arithmetic-related
differences in Hospital, Rayyan and Tax. There are no saved hard-cell flags to
consult: trials contain only `row`, `output`, `parsed`, and, for the five failed
calls, `error`.

This is a behaviorally identified historical scoring convention, **not** a
recovered original scorer revision: the archived historical scorer itself is
the newer target-vote-subtraction/±1 source, and an older source version was not recovered.
The production entry point always uses the bound frozen scorer and retains the
discrepancies. It has no legacy compatibility scoring path. These diagnostic
recomputations do not overwrite frozen summaries or public Movies witnesses,
and must not be presented as newly generated model results.

### Current uniform reanalysis and historical presentation

Current `code/src/paper_tables.py:p1_table` reads the separately hash-bound
[uniform integer derivative](../results/derived/uniform_continuation.json),
not the old summary display values or an arbitrary scorer output file.
Three independent implementations agreed on all 672 compared per-archive integer
quantities. [Provenance and the complete screen definition](../results/derived/uniform-continuation-provenance.md)
identify the audited source hashes and public aggregation boundary.

The current screen uses mode, most-frequent successor, approximate low-cardinality
FDs and previous-value ±1. FD admission is fitted once on the full table, requiring
at most N/2 distinct determinant values and at least 99% modal mapping coverage.
Queried target votes are subtracted from counts, with fixed full-table
first-occurrence tie order, rather than removing and refitting an entire row.
Clean-table +1 counter columns are excluded. Absence is measured in the corresponding
context column. Clean-value leakage uses the clean full-table screen and clean
predecessor, even when the model saw dirty context. This oracle-assisted screen
is retrospective and can over-exclude genuine memory evidence; it is not an
input-matched predictive baseline or an upper bound on memory prevalence.

Current maxima are selected from exact per-archive hard-cell counts before
rounding: DeepSeek anonymous clean **30/375 = .080**, anonymous dirty
**14/200 = .070**, and named clean **32/375 = .085333…**, displayed .085.
Its pooled hard-clean leakage is **3/601 cell-trials**. The Hospital example is
**3/144 = 2.1%**, while naive noninferable accuracy remains **221/468 ≈ 47%**.
Every other model's displayed row and the four open cleaners' **1/2,008**
leakage count remain unchanged. Rates are conditional on parsed rows; repeated
cell-trials in the leakage pool are not necessarily distinct or independent cells.
No quantitative row-continuation figure consumer changes.

`paper_tables_frozen.py` still reads the saved summaries and reproduces the
original 15 tables byte for byte. The old 12 summaries and their 253 differing
leaves remain historical evidence, not silently corrected source archives.
Strict full-row refitting is a separate sensitivity analysis (DeepSeek 3/607;
global maximum and Hospital example unchanged), not the chosen current criterion.

## Tests

```sh
python -m unittest discover -s tests -p test_continuation_scoring.py -v
```

Tests cover hundred-sample-prefix/error-row reconstruction, missing or shuffled
trials, failed and malformed replies, cell denominator handling, exact-row versus
counter-column scoring, hard leakage, legacy schema reporting, hash/symlink
rejection, private mismatch redaction, source-output separation, complete bound
included inventory, and absence of generation/client imports.
