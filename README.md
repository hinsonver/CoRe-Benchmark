# CoRe

**PRIVATE WORKING REPOSITORY — not released publicly. Current manuscript: 2026-10-25.**

Artifact for *Cleaning or Recalling? Disentangling Memorization and World Knowledge in LLM-based Data Cleaning*, by Jingru Yang, Zheng Chen and Ju Fan.

CoRe connects recovery evidence, assigned-value preservation and reference-based repair credit. It compares original tables (O), fresh real records (F), word-name surrogates (W) and syllable-name surrogates (S), alongside separate conflict and reference checks. This revision synchronizes the adopted paper, worked-example figures, seven companions and archived sensitivity checks. The [revision binding](paper/revision-binding.json) identifies the exact manuscript and sources; [revision provenance](paper/revisions/README.md) explains what changed. The scientific results remain frozen; replay does not query a model.

## Quick start

From the repository root, use Python 3.11 or newer and a fresh output directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r environment/requirements-replay.txt
python tools/core.py verify
python tools/core.py reproduce --output build/replayed
python tools/review_diagnostics.py
python tools/check_rayyan.py
python supplements/beers-f-input-provenance/verify.py
```

These commands need no model credentials, GPU, raw-data download or network access after dependency installation. The default replay generates 19 table sources and eleven figure CSVs, including the worked examples and the focused recovery comparison. The diagnostics entry recomputes statistics supported by included numerical evidence and identifies checks supported only by archived aggregates. Use a different output path for another replay.

The [tested runtime](environment/tested-runtime.json) records the local acceptance environment. To pin its three core packages, install [requirements-replay-tested.txt](environment/requirements-replay-tested.txt) instead of the minimum-version requirements.

## Read or check a result

| Task | Start here |
| --- | --- |
| Read the paper | [PDF](paper/latex/main.pdf) or [LaTeX](paper/latex/main.tex) |
| Find a claim and its executable evidence | [Claim map](paper/claim-map.md) |
| Find a displayed figure or table | [Result navigation](docs/results.md) and [label map](paper/result-map.json) |
| Identify this manuscript and presentation revision | [Revision binding](paper/revision-binding.json) and [revision provenance](paper/revisions/README.md) |
| Understand included data and install historical inputs | [Data guide](docs/data.md) |
| Replay, score or inspect source entry points | [Reproduction guide](docs/reproduction.md) |
| Interpret the scope of the checks | [Limitations](docs/limitations.md) |
| Read construction, scoring and extended details | [Manuscript companions](paper/companions/README.md) |
| Check construction/reply sensitivity and output summaries | [Archived diagnostics](paper/companions/07-归档敏感性与输出核验.md) and [offline entry](tools/review_diagnostics.py) |
| Cite this work | [Citation metadata](CITATION.cff) |

The paper has a 12-page body and 14 pages including references, with eight figures, seventeen tables and seven Findings. Its first result figure contrasts missing identifier mappings with retained year candidates. The overview and Hospital construction figure use worked examples. The original condition overview, complete Hospital row and Rayyan plot remain in the extended displays.

The PDF is the adopted manuscript, SHA-256 `04a1c7ee5d7ec992c78fefa6d929319ffb552897ab072eddc94b7ccc2153285d`. The source includes the matching official template and its original class source. This synchronization does not change the [previous fixed private release](https://github.com/hinsonver/CoRe-Benchmark/releases/tag/v0.1.0-a04-review-private-20261022), its tag or its archives.

## Optional exact historical validation

The separate local sibling archive `../CoRe-submission-VE-M01-M05-historical.zip` enables re-scoring of archived Movies replies. Inspect the [data guide](docs/data.md) before using it:

```sh
python tools/data.py status
python tools/data.py install \
  --archive ../CoRe-submission-VE-M01-M05-historical.zip \
  --output ../CoRe-VE-M01-M05-historical-inputs
```

The installer checks the archive and all 289 files and writes only to a new directory outside this repository. Validation additionally requires a truthful external local-use record, as described in the data guide.

The repository remains private. This synchronization does not open reviewer/public access or establish submission eligibility. The historical companion remains separate; do not upload it by default.
