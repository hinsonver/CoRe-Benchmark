# Rayyan retrieval and scoring details

This companion supports the manuscript's reference-quality analysis. Packaged [retrieval status](../../data/provenance/rayyan/retrieval-status.json) and [remote-search provenance](../../data/provenance/rayyan/remote-search.json) describe the retained historical evidence; no new PubMed query or revised ground truth is introduced.

## Audit input and mechanical transformations

The audit uses 1,000 rows and eleven columns with 948 dirty/reference differences. All 722 date differences map `m/d/yy` to `d/int(yy)/mm`, with a two-digit input month in the final position: `1/1/13` to `1/13/01`, and `5/7/09` to `7/9/05`. Of 32 pagination differences, 31 turn ranges into month-name strings, such as `70-6` to `Jun-70`.

## Title-based retrieval

Sampling draws up to 80 cells per error type with seed 0, including all 75 volume/issue, 32 pagination and twelve ISSN cells, for 279 sampled cells. Queries use the reference title, falling back to the dirty title when empty. The first eight ASCII-letter words longer than three characters are joined with AND in the title field; at least two words are required.

Among up to five candidates, the highest title similarity must reach 0.9. Similarity uses `SequenceMatcher` after NFC normalization, case folding, and replacing punctuation and underscores with spaces. There are 152 matched cells and 121 distinct PMIDs. These are automatically selected title matches, not manually certified whole-record matches.

## Field checks and saved counts

| Check | Definition | Population / sampled / matched | Failed reference / passed dirty |
| --- | --- | --- | --- |
| Year | Compare the cell's extracted year with PubMed publication year; 00–26 become 2000–2026 and other two-digit years 1927–1999 | 722 / 80 / 44 | 43 / 42 |
| Changed words | A nonempty set of reference-side changed words must all occur in the PubMed field's case-folded word set; accents remain | 107 / 80 / 38 | 38 / unassessed |
| Volume/issue presence | Reference `-1` and dirty empty strings denote absence; compare field availability, not numerical equality | 75 / 75 / 46 | 28 / 17 |
| Pagination | Match the PubMed page string | 32 / 32 / 18 | 18 / 17 |
| ISSN | Accept print or electronic ISSN | 12 / 12 / 6 | 6 / 0 |

The date field is `article_jcreated_at`; its exact dataset semantics are undocumented, so the test is publication-year consistency. Two reference volumes of `1` pass presence but disagree numerically with saved PubMed volumes `31` and `21` (PMIDs 26452069 and 25819808). Their presence outcomes remain unchanged; the independent numerical differences are carried as annotations. Encoding was checked on the reference side only, hence the unassessed dirty marker.

With N_h error-type populations, m_h matches and b_h failed reference checks, the estimate is the sum of `(N_h/948)*(b_h/m_h)`: 95.2%, interval 91.2%–97.8%. It uses the audit input's 948-cell composition. The 722-cell date stratum carries most weight. The 5,000 bootstrap draws resample saved binary outcomes within matched strata with seed 0 and fixed weights. The interval conditions on the selected matches and field criteria, without matching uncertainty or dependence between cells sharing a PMID.

Saved records include query titles, PMIDs, compared field values and outcomes, the publication year for dates, and a text prefix for encoding. Complete candidate responses, returned titles and similarity scores are not retained. The [archived remote search](../../data/provenance/rayyan/remote-search.json) found matching early JSON/logs/programs but did not recover an additional complete candidate-response chain. [rayyan_audit.py](../../code/src/rayyan_audit.py) describes the historical query/check logic; the public replay uses saved matches and outcomes rather than issuing fresh searches.

## Repair credit and input versions

On the audit input, DeepSeek zero-shot output scores F1 0.002. At zero-based row 120, dirty ISSN `Mar-22` becomes output `0003-3022`, matching saved PMID 8916815, while the reference is `22-Mar`. This output gets no benchmark repair credit.

TabClean's distributed input has 960 differences. It removes commas, represents empty values as `empty`, and has twelve additional dirty-side error positions. Both inputs have 1,000 rows and eleven columns and share the date-conversion pattern. Scoring uses the actual TabClean pair, not the audit pair, and removes the 150 development rows sampled with `random_state=42`.

The remaining 850 rows have 808 errors. There are 498 effective edits and 461 credited repairs, so `F1=2*461/(498+808)=0.71` after rounding. Of the 461 credited repairs, 434 (94%) reproduce the reference date transformation. This is a count of credited output transformations, not a claim about the method's intent or a new externally rescored ranking.

The entry is [tools/check_rayyan.py](../../tools/check_rayyan.py). A04 public replay checks the retained field audit and recounts anonymous outcomes exported from the actual TabClean input/output with the same development exclusion. The raw tables/replies are external; only the optional original-evidence validator re-scores them and regenerates the witnesses. See [Rayyan replay](../../docs/rayyan-replay.md), [release scope](../../docs/release-scope.md), [retrieval status](../../data/provenance/rayyan/retrieval-status.json), [remote-search provenance](../../data/provenance/rayyan/remote-search.json) and [verification guide](05-Public-Verification-Guide.md).

## Other reference examples

Hospital assigns Helen Keller Memorial Hospital in Sheffield, Alabama to Jefferson County in 25 rows, although Sheffield is in Colbert County. Qwen3.8-Max, GLM-5.3 and GPT-6.1-Sol correct 10, 11 and 21 such cells, each scored as a false edit. Movies repeats the same writer in 68 reference cells, for example `Andrew Smith,Andrew Smith`. These examples retain the original benchmark scoring and do not replace the frozen results.
