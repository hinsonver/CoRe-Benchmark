# Data and external original evidence

The default replay needs no data acquisition. [Release scope](release-scope.md) distinguishes included original evidence, numerical witnesses and author-local originals. Source-specific terms are in [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md).

| Material | Location |
| --- | --- |
| Included permitted inputs/replies | `data/`, `artifacts/raw_outputs/`, with source notices |
| Movies numerical witnesses | [movies.json](../data/witnesses/movies.json), unchanged from the accepted candidate |
| New A04 numerical witnesses | [scoped.json](../data/witnesses/scoped.json), [source binding](../data/manifests/SCOPE_SOURCES.json), [witness binding](../data/manifests/SCOPE_WITNESSES.json) |
| Rayyan retained audit and actual-input identity | [Replay guide](rayyan-replay.md), [version chain](../data/provenance/rayyan/version-chain.json) |
| Beers F response/input provenance | [Supplement](../supplements/beers-f-input-provenance/README.md) |
| Exact author-local companion | Separate sibling `../CoRe-release-A04-controlled.zip`; not a public download |

## Install the supplied local companion

```sh
python tools/data.py status
python tools/data.py install \
  --archive ../CoRe-release-A04-controlled.zip \
  --output ../CoRe-A04-local-inputs
```

[SUBMISSION_DATA](../data/manifests/SUBMISSION_DATA.json) binds its exact ZIP and427 members:264 historical dependencies,25 original scoring/entry files and138 newly externalized originals. `BUNDLE.json` is an additional envelope, not a428th data/scorer dependency. Installation checks the entire archive before writing, rejects changed/missing/additional/unsafe members and existing or internal destinations, and never uses the network.

Six large IMDb snapshots are excluded; their source/hash records remain. Current downloads, reconstructed tables and new model replies cannot replace historical bytes. The companion remains author-local until its actual service/input/historical sharing scope is established. A successful technical check does not approve uploading it.

## Validate archived replies

Supply an external JSON local-use record with truthful, nonempty `purpose` and `rights_basis`, `scope` containing `historical_inputs` and `historical_outputs`, and `redistribution:false`. This records the user's actual basis, not a grant or a legal determination; do not invent one to pass a check.

```sh
python tools/core.py validate-private \
  --private-root ../CoRe-A04-local-inputs \
  --authorization-record /external/local-use-record.json \
  --output build/original-validation
```

All402 data/reply dependencies and25 original scoring/entry files are checked before output is created. An isolated temporary overlay executes the original scorers, regenerates Movies and A04 numerical projections and compares them with the public witnesses. This includes84 Movies P2 archives, nine-model Movies conflicts, six additional model/dataset conflict groups, applicable non-Movies P2/aligned scoring and actual TabClean Rayyan scoring. The coverage map identifies150 early Hospital non-spread blocks lacking row mappings; these remain saved-count projections, while2,150 mapped blocks reproduce archived counts. P1 and non-comprehensive E4/E5 checks retain their stated scope. Missing originals or altered hashes fail; public witnesses are not a substitute in this route.

## Acquire only the fixed TabClean Rayyan input pair

This optional route is separate from complete companion validation. The actual dirty/clean pair is pinned to TabClean commit`ae292b6ff8118c8786cd7c97364e9a8a07f00b62`, including exact hashes in [acquire_inputs.py](../tools/acquire_inputs.py). It has960 errors, not the948 of the Raha audit table. Review the upstream terms before obtaining files; downloading them does not authorize rehosting.

Verify files you already possess:

```sh
python tools/acquire_inputs.py rayyan-inputs \
  --from-directory /external/supplied-pair \
  --destination ../CoRe-Rayyan-inputs
```

Or explicitly fetch those two fixed URLs after reviewing the source:

```sh
python tools/acquire_inputs.py rayyan-inputs --fetch \
  --acknowledge-source-terms --destination ../CoRe-Rayyan-inputs
```

Both modes require a new external directory and validate hashes before installation. They reject symlinks, overwrite and destinations in the public tree. Fetch refuses redirects and is never invoked by offline replay. The pair alone is not the427-file companion and does not supply a historical output or complete raw validator closure.
