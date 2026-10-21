# CoRe

**LAYERED RELEASE PREPARATION — not released.**

Artifact for *Cleaning or Recalling? Disentangling Memorization and World Knowledge in LLM-based Data Cleaning*, by Jingru Yang, Zheng Chen and Ju Fan.

CoRe connects recovery evidence, assigned-value preservation and reference-based repair credit. This version contains the VE-M01–M05 paper, synchronized display sources and offline verification. The [revision binding](paper/revision-binding.json) identifies the manuscript; the [release scope](docs/release-scope.md) identifies which evidence is supplied as records and which as numerical witnesses. Scientific results remain frozen. Replay makes no model calls.

## Quick start

From the extracted `CoRe-release-A04` directory, use Python 3.11 or newer and a fresh output directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r environment/requirements-replay.txt
python tools/core.py verify
python tools/core.py reproduce --output build/replayed
python tools/check_screening.py
python tools/check_rayyan.py
python supplements/beers-f-input-provenance/verify.py
```

After dependency installation these commands work offline, without model credentials, a GPU or data downloads. They regenerate 19 current table sources and nine figure CSVs. The [tested runtime](environment/tested-runtime.json) and [tested requirements](environment/requirements-replay-tested.txt) record the acceptance environment.

## Read or verify a result

| Task | Start here |
| --- | --- |
| Read the paper | [PDF](paper/latex/main.pdf), [LaTeX](paper/latex/main.tex) |
| Locate C1–C3 and their verification routes | [Claim map](paper/claim-map.md) |
| Locate a displayed figure or table | [Result guide](docs/results.md), [label map](paper/result-map.json) |
| Distinguish record scoring from statistical replay | [Release scope](docs/release-scope.md), [reproduction](docs/reproduction.md) |
| Inspect included data or optional external inputs | [Data guide](docs/data.md) |
| Read source-specific permissions and attribution | [Third-party notices](THIRD_PARTY_NOTICES.md) |
| Read detailed construction and scoring rules | [Six manuscript companions](paper/companions/README.md) |
| Identify or cite this version | [Revision provenance](paper/revisions/README.md), [CITATION](CITATION.cff) |

The unchanged paper has a 12-page body and 14 pages including references, with seven figures, eighteen tables and seven Findings. Plot rendering can vary with fonts; table bodies and numerical CSVs are the scientific comparison targets.

## Optional author-local original-evidence validation

The separate `../CoRe-release-A04-controlled.zip` contains 427 exact dependencies/scorer files plus its bundle envelope. It combines 289 historical files with 138 originals withheld from this public-preparation tree. It is **author-local, controlled pending review**, not a public download or a reviewer delivery already approved. Do not upload it by default.

```sh
python tools/data.py status
python tools/data.py install \
  --archive ../CoRe-release-A04-controlled.zip \
  --output ../CoRe-A04-local-inputs
```

The optional validator additionally needs a truthful external local-use record; see [data instructions](docs/data.md#validate-archived-replies). It regenerates both numerical witness layers using the exact supplied originals and historical scoring code before producing replayed results. Public replay does not require this companion or silently read it.

This assembly creates no release, DOI, external access link or permission grant. Actual material delivery and final publication approval remain separate. The code's MIT license does not relicense datasets, templates, model weights or third-party output. See the [scope and notice guide](THIRD_PARTY_NOTICES.md).
