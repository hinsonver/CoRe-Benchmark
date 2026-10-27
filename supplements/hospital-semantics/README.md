# Hospital relationships and archived edits

This audit uses the existing Hospital dirty/reference tables and eight cleaners' archived
20-row spread-chunk replies. It does not generate new inputs or call a model or retrieval API.

From the repository root, choose a new output directory:

```sh
python3 supplements/hospital-semantics/audit.py --repo-root . --output /new/hospital-audit
python3 supplements/hospital-semantics/test_audit.py
```

Only the Python standard library is required. `sources.json` binds the input CSVs and reply
files. `relations.csv` checks column mappings and retained non-identity values. `edits.csv`
gives effective geographic edits with reply, chunk and row addresses. `runs.csv` checks the
original error, prediction, detection and repair counts; `surrogate-column-counts.csv`
aggregates the 48 surrogate runs. These are cell-edits across model/construction runs, not
independent hospital counts or a causal estimate of geographic conflicts. The main paper's
identity-column score excludes State. The technical report explains the interpretation.

At exact half-way four-decimal boundaries, floating-point harmonic and integer F1 formulas
can round differently in the last displayed digit. The audit strictly checks every integer
count and checks F1 against its display-rounding interval. It does not change the original
scores or their statistical inputs.
