# CoRe

**Public research repository. Manuscript and report: 2026-11-01.**

The paper is available as an [arXiv preprint (2611.08106)](https://arxiv.org/abs/2611.08106).

Artifact for *Cleaning or Recalling? Knowledge Dependence in LLM-based Data Cleaning*, by Jingru Yang, Honglu Zhang, Jiayi Mi, Ju Fan, Zheng Chen and Xiaoyong Du.

Corresponding author: Zheng Chen (202301050@muc.edu.cn).

CoRe compares original tables (O), fresh real records (F), word-based surrogates (W) and syllable-based surrogates (S), alongside assigned-value and reference checks. Read the [paper](paper/latex/main.pdf) and [supplementary technical report](paper/CoRe-Supplementary-Technical-Report.pdf). The [document binding](paper/revision-binding.json) identifies their sources. Figure 6 shows DeepSeek cluster intervals and three-run Baran means without error bars. The [entity/reply inference guide](docs/cluster-inference.md) specifies the numerical witnesses, 40-comparison and Beers families, reply-cluster conflict intervals and all-or-none displays. No model is queried.

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
| Read the paper | [arXiv](https://arxiv.org/abs/2611.08106), [repository PDF](paper/latex/main.pdf) or [LaTeX](paper/latex/main.tex) |
| Find a claim and its executable evidence | [Claim map](paper/claim-map.md) |
| Find a displayed figure or table | [Result navigation](docs/results.md) and [label map](paper/result-map.json) |
| Identify this manuscript and presentation revision | [Revision binding](paper/revision-binding.json) and [revision provenance](paper/revisions/README.md) |
| Understand included data and install historical inputs | [Data guide](docs/data.md) |
| Download the fixed historical materials | [GitHub download and installation](docs/github-delivery.md) |
| Replay, score or inspect source entry points | [Reproduction guide](docs/reproduction.md) |
| Inspect every experiment family | [Coverage matrix](REPRODUCTION.json), [continuation scoring](docs/continuation-scoring.md), [baseline scoring](docs/baseline-scoring.md) and [execution plans](docs/experiment-execution.md) |
| Interpret the scope of the checks | [Limitations](docs/limitations.md) |
| Read construction, scoring and extended details | [Technical report](paper/CoRe-Supplementary-Technical-Report.pdf) and [seven-section index](paper/CoRe-companion-index.md) |
| Check construction/reply sensitivity and output summaries | [Technical details](paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-7), [cluster inference](docs/cluster-inference.md) and [offline diagnostics](tools/review_diagnostics.py) |
| Cite this work | [Citation metadata](CITATION.cff) |

The paper has a 12-page body and 14 pages including references, with eight figures, seventeen tables and seven Findings. Its first result figure contrasts missing identifier mappings with retained year candidates. The overview and Hospital construction figure use worked examples. The original condition overview, complete Hospital row and Rayyan plot remain in the extended displays.

The main PDF has SHA-256 `d69cd04f7444876129f34bcf4fea899ce6974bffef8a0f32a51a3c462918d96d`; the technical report has SHA-256 `14356913cefa9229a8ffdec1ca367ffaca43e08b56ead8267071651573055b85`. The report has 24 pages, seven sections, 18 tables and seven figures. This checkout contains the current six-author manuscript and its matching report; the fixed `v0.2.0` core ZIP remains the earlier snapshot. The [statistical methods and replay](docs/cluster-inference.md) describe the entity/reply weights, complete Holm families, conflict denominators and anonymous numerical witnesses. The [Hospital relationship/edit audit](supplements/hospital-semantics/README.md) and [entity/reply and year-choice diagnostics](supplements/dependence-and-year/README.md) provide deterministic checks using existing inputs and replies.

## Optional exact historical validation

This repository hosts `CoRe-submission-VE-M01-M05-historical.zip` as a separate, publicly downloadable Release asset, alongside `CoRe-review-core-20261026.zip` and `SHA256SUMS`. The default statistical core still contains no raw Movies records or replies. Follow the [download and installation guide](docs/github-delivery.md), then inspect the [data guide](docs/data.md). With the downloaded archive outside this checkout:

```sh
python tools/data.py status
python tools/data.py install \
  --archive /absolute/downloads/CoRe-submission-VE-M01-M05-historical.zip \
  --output ../CoRe-VE-M01-M05-historical-inputs
```

The installer checks the archive and all 289 files and writes only to a new directory outside this repository. Validation additionally requires a truthful external local-use record, as described in the data guide.

The repository and its existing Release assets are publicly accessible without a GitHub account. Public access does not change the applicable third-party terms or resolve the historical evidence limits described above. The historical companion remains outside the current Git tree and default statistical core; readers must supply their own truthful local-use record as described in the data guide. The software license does not relicense third-party data or archived replies.
