# CoRe

**LOCAL SUBMISSION CANDIDATE — not released.**

Artifact for *Cleaning or Recalling? Disentangling Memorization and World Knowledge in LLM-based Data Cleaning*, by Jingru Yang, Zheng Chen and Ju Fan.

CoRe connects recovery evidence, assigned-value preservation and reference-based repair credit. It compares original tables (O), fresh real records (F), word-name surrogates (W) and syllable-name surrogates (S), alongside separate conflict and reference checks. This repository contains the paper after VE-M01–M05, synchronized presentation sources, archived evidence, numerical Movies witnesses, scoring tools and offline replay. The [revision binding](paper/revision-binding.json) identifies the exact manuscript and sources; [revision provenance](paper/revisions/README.md) explains what changed. The scientific results remain frozen; replay does not query a model.

## Quick start

From the extracted `CoRe-submission-VE-M01-M05` directory, use Python 3.11 or newer and a fresh output directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r environment/requirements-replay.txt
python tools/core.py verify
python tools/core.py reproduce --output build/replayed
python tools/check_rayyan.py
python supplements/beers-f-input-provenance/verify.py
```

These commands need no model credentials, GPU, raw-data download or network access after dependency installation. The default replay generates the current presentation: 19 table sources and nine figure CSVs for eight plot source groups. Use a different output path for another replay.

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
| Cite this work | [Citation metadata](CITATION.cff) |

The paper has a 12-page body and 14 pages including references, with seven figures, eighteen tables and seven Findings. The full eight-model scale figure and the full aligned/whole-table matrix are in the main paper. The Rayyan plot remains available as an extended display.

## Optional exact historical validation

The separate local sibling archive `../CoRe-submission-VE-M01-M05-historical.zip` enables re-scoring of archived Movies replies. Inspect the [data guide](docs/data.md) before using it:

```sh
python tools/data.py status
python tools/data.py install \
  --archive ../CoRe-submission-VE-M01-M05-historical.zip \
  --output ../CoRe-VE-M01-M05-historical-inputs
```

The installer checks the archive and all 289 files and writes only to a new directory outside this repository. Validation additionally requires a truthful external local-use record, as described in the data guide.

This local assembly does not establish submission eligibility. An actual data delivery or hosting path and explicit publication approval remain separate decisions. Neither this repository nor its historical companion archive has been published by this assembly; do not upload the historical companion by default.
