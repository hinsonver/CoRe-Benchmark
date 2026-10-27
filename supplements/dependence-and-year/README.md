# Entity/reply incidence and year-choice diagnostics

These deterministic calculations use archived inputs and replies. They do not call a model,
rerun PubMed retrieval, generate bootstrap samples, or replace the reported intervals and tests.
The aggregate CSVs support technical-report Sections 7.9 and 7.10.

- `hospital-graphs.csv` describes the entity/reply incidence of ten Hospital inputs.
- `hospital-delete-one.csv` contains all 120 model/seed/contrast deletion summaries, including
  the auxiliary O-F comparison that crosses zero for Qwen2.5-14B at seed 0.
- `conflict-graphs.csv` describes known-target grouping for 240 settings across the eight main models.
- `year-grouped-counts.csv` and `year-choice-transitions.csv` give aggregate Movies counts.
- `sources.json` binds the inputs used in the calculation. Historical movie members are checked
  against `data/manifests/CORE_SOURCES.json`, not substituted by public numerical projections.

From the repository root, supply the existing historical ZIP and a new output directory:

```sh
python3 supplements/dependence-and-year/diagnostics.py \
  --repo-root . \
  --historical-zip /external/CoRe-submission-historical.zip \
  --output /new/dependence-and-year
python3 supplements/dependence-and-year/test_diagnostics.py
```

The historical ZIP is required for raw Movies validation; aggregate files alone do not
reconstruct its entity/reply assignments. The output also includes row-level movie comparisons
in `year-private-paired-rows.csv`. That file is not included in this statistical-core directory.

Hospital deletions remove one hospital's counts from fixed saved outputs. Paired comparisons
omit the same hospital from both sides; fresh comparisons omit one hospital from one side at
a time. These ranges measure output composition, not new confidence intervals or model
responses to a modified prompt. The joint entity/reply dependence remains outside the original
uncertainty calculation; positive deletion ranges do not establish its coverage guarantee.
