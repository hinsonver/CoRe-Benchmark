# Rayyan actual input, repair credit and saved field audit

```sh
python tools/check_rayyan.py
```

This standard-library entry checks [RAYYAN_REPLAY](../data/manifests/RAYYAN_REPLAY.json), [SCOPE_WITNESSES](../data/manifests/SCOPE_WITNESSES.json) and their exact hashes. Public replay uses anonymous cell outcomes exported from the actual TabClean input/output; its raw tables remain external. [Source/version identity](../data/provenance/rayyan/version-chain.json) distinguishes that960-error input from the948-error Raha audit table. Neither is substituted for the other.

## Repair-credit recount

Excluding the saved150 development rows leaves850 rows:808 errors,498 effective edits,497 detections and461 credited repairs. Of the latter,434 reproduce the reference date transformation (94%, rounded); repair F1 rounds to0.71. Error/change/repair/date flags are recounted cell by cell, not copied from a saved final score. The optional original-evidence validator re-exports these flags from the exact external input/output using the original scorer before comparing the recount.

The [fixed input importer](../tools/acquire_inputs.py) can verify or explicitly acquire just the pinned input pair into an external directory. It is not needed for public replay and does not authorize rehosting. [Data instructions](data.md) distinguish the pair from the complete controlled companion.

## Saved field-check replay

The independent279-cell sample contains152 matched cells and121 distinct PMIDs. Saved checks and the948-cell type composition reproduce95.2% weighted reference-check failure and91.2%–97.8% interval;114 scalar comparisons are rechecked. Volume/issue tests concern presence. Two unequal saved volumes remain annotations, encoding dirty-side agreement is unassessed, and full encoding metadata is not independently rejudged. See [M06 criteria](../data/provenance/rayyan/m06-criteria.json) and [the detailed companion](../paper/companions/03-Rayyan检索与评分材料说明.md).

## Historical retrieval evidence

**Historical NLM-derived field evidence, not a current PubMed service or current NLM dataset.** Saved query titles, selected PMIDs, simplified fields and author judgments are attributed to NLM/PubMed; they do not imply NLM endorsement. No abstracts or full-text content are supplied. Full candidate responses, returned titles, similarity scores, complete metadata and unmatched reasons were not recovered. The [retrieval inventory](../data/provenance/rayyan/retrieval-status.json) and [remote search record](../data/provenance/rayyan/remote-search.json) preserve that distinction. A new query is not a historical response.
