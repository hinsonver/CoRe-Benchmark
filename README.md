# CoRe

**PRIVATE REVIEW PRERELEASE — not released publicly. Current manuscript and report: 2026-10-26.**

Artifact for *Cleaning or Recalling? Disentangling Memorization and World Knowledge in LLM-based Data Cleaning*, by Jingru Yang, Zheng Chen, Ju Fan and Xiaoyong Du.

CoRe connects recovery evidence, assigned-value preservation and reference-based repair credit. It compares original tables (O), fresh real records (F), word-name surrogates (W) and syllable-name surrogates (S), alongside separate conflict and reference checks. Read the current [paper](paper/latex/main.pdf) with the [22-page supplementary technical report](paper/CoRe-Supplementary-Technical-Report.pdf). The [revision binding](paper/revision-binding.json) identifies their exact bytes and current presentation sources; [revision provenance](paper/revisions/README.md) separates historical records from current reading. Existing replies and input tables are preserved. The current continuation display uses uniform re-scoring, and Beers city tests apply Holm before rounding; no model is queried. See the [statistical revision note](docs/statistical-revisions.md).

## Quick start

From the repository root, use Python 3.11 or newer and a fresh output directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r environment/requirements-replay.txt
python tools/core.py verify
python tools/reproduce_all.py --output build/all-offline
```

The unified entry needs no model credentials, GPU or network after dependency installation. It generates and byte-compares 19 current table sources, eleven figure CSVs and 15 original frozen table sources, runs the raw continuation and baseline scorers, checks Rayyan, screening and Beers provenance, and inspects eight original experiment plans. It writes `coverage.json` and `coverage.md` under the selected new output directory.

Fresh model runs use **the reviewer's own API key and account**, not an author key. The [execution guide](docs/experiment-execution.md#reviewer-configuration-and-model-identity) separates offline configuration checks, optional model-catalogue lookup and explicitly confirmed generation. Historical replay stays key-free. The fixed `v0.2.0` downloads preserve the earlier entrypoint; use this updated checkout for reviewer-owned hosted execution.

For these archived runs, a completed coverage run returns **exit 2**, meaning execution completed with documented historical limits. Exit 1 identifies an unexpected execution failure. Twelve early continuation summaries disagree with the bound scorer in the full historical check (ten in the included subset); twelve whole-table Baran runs lack saved corrections. The [coverage matrix](REPRODUCTION.json) and [scope guide](docs/limitations.md) distinguish these from unavailable external access. Do not suppress a nonzero exit or describe it as complete raw-result agreement. The original `python tools/core.py reproduce --output build/replayed` generates the corrected current display; add `--presentation frozen` for the original archived scores and formatting.

The [tested runtime](environment/tested-runtime.json) records the local acceptance environment. To pin its three core packages, install [requirements-replay-tested.txt](environment/requirements-replay-tested.txt) instead of the minimum-version requirements.

## Read or check a result

| Task | Start here |
| --- | --- |
| Read the paper | [PDF](paper/latex/main.pdf) or [LaTeX](paper/latex/main.tex) |
| Find a claim and its executable evidence | [Claim map](paper/claim-map.md) |
| Find a displayed figure or table | [Result navigation](docs/results.md) and [label map](paper/result-map.json) |
| Identify this manuscript and presentation revision | [Revision binding](paper/revision-binding.json) and [revision provenance](paper/revisions/README.md) |
| Understand included data and install historical inputs | [Data guide](docs/data.md) |
| Download the fixed private delivery | [GitHub download and installation](docs/github-delivery.md) |
| Replay, score or inspect source entry points | [Reproduction guide](docs/reproduction.md) |
| Inspect every experiment family | [Coverage matrix](REPRODUCTION.json), [continuation scoring](docs/continuation-scoring.md), [baseline scoring](docs/baseline-scoring.md) and [execution plans](docs/experiment-execution.md) |
| Interpret the scope of the checks | [Limitations](docs/limitations.md) |
| Read construction, scoring and extended details | [Technical report](paper/CoRe-Supplementary-Technical-Report.pdf) and [seven-section index](paper/CoRe-companion-index.md) |
| Check construction/reply sensitivity and output summaries | [Archived diagnostics](paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-7) and [offline entry](tools/review_diagnostics.py) |
| Cite this work | [Citation metadata](CITATION.cff) |

The paper has a 12-page body and 14 pages including references, with eight figures, seventeen tables and seven Findings. Its first result figure contrasts missing identifier mappings with retained year candidates. The overview and Hospital construction figure use worked examples. The original condition overview, complete Hospital row and Rayyan plot remain in the extended displays.

The main PDF has SHA-256 `2b6e5fdd814658307f77e1d1da86fa699c574ecd100474a0838598a206ff2e8e`; the technical report has SHA-256 `ce23abbc850bcd4ac4df205bddf31d49569423d8e501e75193ae2388914c090c`. Both are exact copies of the current four-author reading documents. The report has seven sections, fourteen tables and seven original figures. Its PDF replaces the former seven Markdown reports as the formal scholarly reading document; the Markdown versions remain in repository history. The source includes the matching official template and its original class source. The [current private prerelease](https://github.com/hinsonver/CoRe-Benchmark/releases/tag/v0.2.0-review-private-20261026) does not change the [previous fixed private release](https://github.com/hinsonver/CoRe-Benchmark/releases/tag/v0.1.0-a04-review-private-20261022), its tag or its archives. Records under `paper/revisions/` and the retained author-side frozen-claims snapshot are historical provenance, not current reader instructions.

## Optional exact historical validation

The same private GitHub repository hosts `CoRe-submission-VE-M01-M05-historical.zip` as a separate Release asset, alongside `CoRe-review-core-20261026.zip` and `SHA256SUMS`. The default statistical core still contains no raw Movies records or replies. Follow the [authenticated download and installation guide](docs/github-delivery.md), then inspect the [data guide](docs/data.md). With the downloaded archive outside this checkout:

```sh
python tools/data.py status
python tools/data.py install \
  --archive /absolute/downloads/CoRe-submission-VE-M01-M05-historical.zip \
  --output ../CoRe-VE-M01-M05-historical-inputs
```

The installer checks the archive and all 289 files and writes only to a new directory outside this repository. Validation additionally requires a truthful external local-use record, as described in the data guide.

The repository remains private. Private hosting does not establish a reviewer's actual access, public availability, submission eligibility or a blanket third-party redistribution right. The historical companion remains outside the Git tree and default statistical core; readers must supply their own truthful local-use record, not reuse the authors' declaration as proof of rights.
