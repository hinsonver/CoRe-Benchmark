# Uniform continuation reanalysis

`uniform_continuation.json` is a separately bound numerical reanalysis of 168
saved continuation archives (9,600 trials). It contains per-archive summaries,
integer numerators and denominators, anonymous per-column counts, source hashes
and the scoring definition. It contains no Movie records or model replies.
The original archives, their saved summaries, the original source bindings and
the 15 historical reference tables are retained unchanged.

The selected `current_full` criterion is an oracle-assisted structural screen
fitted to the full source table: column mode, most-frequent successor,
approximate low-cardinality functional dependencies (at most N/2 distinct
determinant values and at least 99% modal mapping coverage), and previous-value
plus or minus one. Queried target votes are subtracted from counts, retaining
full-table first-occurrence tie order and full-table FD admission; this is not a
strict row-held-out refit. Clean-table +1 counter columns are omitted entirely.
Absence means absence from the corresponding context column. Dirty-context
continuation targets the dirty next-row value; clean-value leakage is screened
against the clean full table and clean predecessor, not just the model's input.

Accuracy denominators contain scored cells in parsed rows. Pooled leakage uses
repeated cell-trials, not necessarily distinct cells or independent observations.
The screen can exclude genuine memory; low residual accuracy is not an upper
bound on memorization or contamination. Its supported interpretation is no
positive continuation evidence attributable to row memory after these exclusions.

Three independent implementations agreed on all 672 compared per-archive integer
quantities. The retained audit and its summary are identified by exact hashes in
the provenance, together with the aggregate export source. Public replay verifies
the new derivative and original available source bytes; excluded Movie sources
remain identified by the unchanged private-source hash bindings. Public replay
does not re-read or re-score those excluded raw records.

Current table generation selects dataset maxima directly from exact hard-cell
counts and sums the dirty-context hard-leakage counts. DeepSeek's anonymous
clean/dirty maxima are 30/375 and 14/200; its named clean maximum is 32/375
(displayed .085), and pooled hard-clean leakage is 3/601. The 12 earlier archives
with 253 differing summary leaves remain historical mixed-scoring evidence; no
claim is made that their original scoring source was recovered. Strict full-row
refitting is a separate sensitivity analysis (3/607), not the selected screen.

`code/src/uniform_continuation.py` and the current `paper_tables.py` consume this
new binding. The `original_files` and `private_code` hashes in `CORE_SOURCES.json`
continue to identify the historical sources, not attest the new current code;
`paper_tables_frozen.py` continues to reproduce the old
15-table presentation.

The current Beers table separately computes two-sided sign-test probabilities
from the saved chunk integers before Holm correction and rounds only the final
adjusted probabilities. DeepSeek and Qwen3.8 display .646 and .154; the other six
display 1.000. Historical `scale_summary.json` probabilities and frozen-table
replay remain unchanged; bootstrap O-S comparisons and significance do not change.
