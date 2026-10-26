# Data and historical inputs

The default replay uses the evidence already in this repository. No raw-data acquisition is needed to reproduce its statistical products.

| Material | Location and use |
| --- | --- |
| Included non-Movies controlled tables and archived replies | `data/` and `artifacts/raw_outputs/`; frozen inputs for the included scoring and replay routes |
| Numerical Movies witnesses | [movies.json](../data/witnesses/movies.json); block counts, anonymous conflict events and saved summary projections without row-level Movies records or replies |
| Witness and source bindings | [CORE_WITNESSES.json](../data/manifests/CORE_WITNESSES.json), [CORE_SOURCES.json](../data/manifests/CORE_SOURCES.json) |
| Rayyan saved retrieval evidence and scoring inputs | [Replay guide](rayyan-replay.md) and [Rayyan companion](../paper/CoRe-Supplementary-Technical-Report.pdf#nameddest=companion-3) |
| Beers F historical/final input provenance | [Supplement README](../supplements/beers-f-input-provenance/README.md) and its verifier |
| Optional exact historical Movies dependencies | Separate local sibling archive `../CoRe-submission-VE-M01-M05-historical.zip`; not part of the repository |

## Inspect and install the local historical archive

```sh
python tools/data.py status
python tools/data.py install \
  --archive ../CoRe-submission-VE-M01-M05-historical.zip \
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

This entry checks the historical dependencies and scorer hashes before re-scoring saved Movies cleaning, aligned and conflict outputs and comparing them with the numerical witnesses. Its scope is the 84 archived direct-editing runs, the archived aligned setting and the nine-model conflict evidence. The continuation probe still uses saved summaries; archived whole-table runs are not all independently re-scored by this route. See [reproduction](reproduction.md) for the other scoring entries.

## Access and redistribution

The historical companion contains row-level historical records and replies. Local possession, local use, redistribution and reviewer delivery are separate questions; assembly and a successful hash check do not answer them. No public data URL or reviewer access path is implied. Arrange an appropriate delivery or hosting path and obtain explicit publication approval before any release. Follow the applicable source terms and the repository's licensing notices; the code license does not grant rights in third-party data.
