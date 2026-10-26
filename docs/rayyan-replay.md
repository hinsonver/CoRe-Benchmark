# Rayyan input, scoring and audit replay

```sh
python tools/check_rayyan.py
```

The entry uses only the standard library. It validates the versions listed in
[RAYYAN_REPLAY.json](../data/manifests/RAYYAN_REPLAY.json), including the actual
TabClean input/output and development-row indices, before scoring. It does not
query PubMed or substitute the audit table for TabClean's input.

## Repair-credit scoring

The audit table has 948 dirty/reference differences; TabClean's distributed input
has 960. After excluding 150 development rows from the latter, 850 rows contain
808 errors, 498 effective edits, 497 detected errors and 461 credited repairs.
Of these credited repairs, 434 reproduce the reference date conversion. The
rounded F1 is 0.71 and the credited-conversion share is 94%.

Input commits/blobs and serialization differences are recorded in
[version-chain.json](../data/provenance/rayyan/version-chain.json).

## Saved field-check replay

The 279 sampled cells yield 152 matched cells and 121 distinct PMIDs. Using the
948-cell type composition, the saved field-check outcomes reproduce the 95.2%
weighted reference-check failure estimate and 91.2%–97.8% interval. The entry
also rechecks 114 scalar comparisons. Volume/issue tests concern presence;
two unequal saved volumes remain independent annotations. Encoding dirty-side
agreement is unassessed, and full encoding metadata is not independently rejudged.

See [the criteria decision](../data/provenance/rayyan/m06-criteria.json) and
[the detailed companion](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-3).

## Historical retrieval provenance

Saved query titles, selected PMIDs, simplified values, outcomes, the earlier sample
and matching progress records are retained. Full candidate responses, returned
titles, similarity scores, full metadata and unmatched-reason codes were not
recovered within the documented searches. A new response is not a historical one.
The exact available/missing inventory and search scope remain in
[retrieval-status.json](../data/provenance/rayyan/retrieval-status.json) and
[remote-search.json](../data/provenance/rayyan/remote-search.json).
