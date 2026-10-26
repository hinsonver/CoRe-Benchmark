# Data and historical inputs

The default replay uses the evidence already in this repository. No raw-data acquisition is needed to reproduce its statistical products.

| Material | Location and use |
| --- | --- |
| Included non-Movies controlled tables and archived replies | `data/` and `artifacts/raw_outputs/`; frozen inputs for the included scoring and replay routes |
| Numerical Movies witnesses | [movies.json](../data/witnesses/movies.json); block counts, anonymous conflict events and saved summary projections without row-level Movies records or replies |
| Witness and source bindings | [CORE_WITNESSES.json](../data/manifests/CORE_WITNESSES.json), [CORE_SOURCES.json](../data/manifests/CORE_SOURCES.json) |
| Current uniform continuation reanalysis | [Integer aggregates](../results/derived/uniform_continuation.json), [separate binding](../data/manifests/UNIFORM_CONTINUATION.json) and [provenance](../results/derived/uniform-continuation-provenance.md); original saved witnesses remain historical |
| Rayyan saved retrieval evidence and scoring inputs | [Replay guide](rayyan-replay.md) and [Rayyan companion](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-3) |
| Beers F historical/final input provenance | [Supplement README](../supplements/beers-f-input-provenance/README.md) and its verifier |
| Optional exact historical Movies dependencies | `CoRe-submission-VE-M01-M05-historical.zip`, a separate Release asset in the same private repository; not in the Git tree or default statistical core |

## Download, inspect and install historical inputs

Use the [fixed private GitHub delivery](github-delivery.md) to authenticate, download the two ZIP assets and checksum file, and check their hashes. Downloading requires actual access to `hinsonver/CoRe-Benchmark`; the existence of a private asset does not establish reviewer access. After downloading the historical ZIP outside this checkout:

```sh
python tools/data.py status
python tools/data.py install \
  --archive /absolute/downloads/CoRe-submission-VE-M01-M05-historical.zip \
  --output ../CoRe-VE-M01-M05-historical-inputs
```

[SUBMISSION_DATA.json](../data/manifests/SUBMISSION_DATA.json) binds the exact companion archive. The installer verifies its SHA-256 and the exact set and hashes of 289 files: 264 historical dependencies and 25 scorer/code files, plus the archive's `BUNDLE.json` metadata. It checks that this metadata agrees with the repository manifest. It rejects changed, missing, additional or unsafe members, an existing destination, and a destination inside the repository. It does not overwrite files or use the network.

Keep the installed historical directory outside the repository. It supplies the exact inputs, archived replies and scoring code expected by the historical validation entry. Six large upstream IMDb snapshots are not duplicated in the companion; their provenance and hashes remain recorded in the source metadata. A current IMDb download, a reconstructed table or a new model response cannot replace the historical bytes.

## Validate archived replies

First prepare an external JSON local-use record identifying the actual `purpose` and `rights_basis`. Its `scope` must include both `historical_inputs` and `historical_outputs`, and `redistribution` must be `false`. Keep the record outside the repository. Do not copy a fictional rights statement to make validation pass: the record is a declaration by the user, not legal proof or a grant of rights.

With that record at the path shown below:

```sh
python tools/core.py validate-private \
  --private-root ../CoRe-VE-M01-M05-historical-inputs \
  --authorization-record /external/local-use-record.json \
  --output build/historical-validation
```

This entry checks the historical dependencies and scorer hashes before re-scoring saved Movies cleaning, aligned and conflict outputs and comparing them with the numerical witnesses. Its scope is the 84 archived direct-editing runs, the archived aligned setting and the nine-model conflict evidence. It does not rejudge continuation replies: current continuation display uses the separately bound uniform integer derivative, while frozen display retains saved summaries. Archived whole-table runs are not all independently re-scored by this route. See [reproduction](reproduction.md) for the other scoring entries.

For the integrated check, supply the same installation and local-use record to:

```sh
python tools/reproduce_all.py --output build/all-with-history \
  --historical-root ../CoRe-VE-M01-M05-historical-inputs \
  --authorization-record /external/local-use-record.json
```

This also invokes the separate raw continuation and baseline scorers. It does not upgrade a missing correction list to raw validation or resolve a scoring-version discrepancy through a saved-summary fallback. A technically completed check retains exit 2 and its explicit coverage limits.

## Access and redistribution

The historical companion contains row-level historical records and replies and is hosted as a private Release asset in this same repository. Its fixed URL and authentication instructions are in the [delivery guide](github-delivery.md). Local possession, local use, further redistribution and reviewer access are separate questions; hosting and a successful hash check do not answer them. No public data release or verified reviewer access is implied. Public publication or wider sharing requires separate approval and compliance with applicable source terms and the repository's licensing notices; the code license does not grant rights in third-party data. Each reader must truthfully record their own local-use basis; an author-side declaration is not reviewer proof of rights.
