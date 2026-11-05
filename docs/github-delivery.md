# Obtain the current checkout and fixed historical materials

The `main` checkout in the public `hinsonver/CoRe-Benchmark` repository contains the current paper, 24-page technical report and matching statistical display. No GitHub account is required:

```sh
git clone https://github.com/hinsonver/CoRe-Benchmark.git
cd CoRe-Benchmark
git rev-parse HEAD
```

Record that commit identifier when reporting a reproduction. The [README](../README.md#quick-start) gives the current offline commands. The paper and report are linked there and bound by SHA-256 in [the document binding](../paper/revision-binding.json).

The retained [2026-10-26 prerelease](https://github.com/hinsonver/CoRe-Benchmark/releases/tag/v0.2.0-review-private-20261026) has three fixed assets. The word `private` in its tag records its original hosting status; the assets are now public:

| Asset | Purpose |
| --- | --- |
| `CoRe-review-core-20261026.zip` | Earlier four-author paper, 22-page technical report and code snapshot, non-Movies raw evidence and numerical Movies witnesses; no raw Movies records or replies |
| `CoRe-submission-VE-M01-M05-historical.zip` | Exact historical Movies inputs, archived replies and bound historical code, separate from the Git tree and statistical core |
| `SHA256SUMS` | SHA-256 checksums of both ZIP assets |

Both this fixed snapshot and the [previous fixed release](https://github.com/hinsonver/CoRe-Benchmark/releases/tag/v0.1.0-a04-review-private-20261022), their tags and asset bytes are unchanged. Use the checkout for the current paper and inference display; use the fixed tag above to acquire exact historical inputs or reproduce the older core snapshot. Do not use a moving `latest` URL or mistake an automatically generated source-code ZIP for the separate historical asset.

## Download without signing in

Download the three assets with a browser or the following commands. These public URLs require no token or API key:

```sh
CORE_DOWNLOAD_DIR="$(mktemp -d)"
CORE_RELEASE_URL="https://github.com/hinsonver/CoRe-Benchmark/releases/download/v0.2.0-review-private-20261026"
for CORE_ASSET in CoRe-review-core-20261026.zip CoRe-submission-VE-M01-M05-historical.zip SHA256SUMS; do
  curl --fail --location "$CORE_RELEASE_URL/$CORE_ASSET" --output "$CORE_DOWNLOAD_DIR/$CORE_ASSET" || exit 1
done
(cd "$CORE_DOWNLOAD_DIR" && shasum -a 256 -c SHA256SUMS)
```

The temporary download directory is outside the repository. Stop if either checksum fails. The historical ZIP's fixed SHA-256 is `9569fe9d6d475ea0243b5d9a04f2a8ed098557873ffca7597cbcb6eef67bbc09`.

Its stable asset URL is [the historical ZIP](https://github.com/hinsonver/CoRe-Benchmark/releases/download/v0.2.0-review-private-20261026/CoRe-submission-VE-M01-M05-historical.zip). The download is public. If it fails, report the URL and HTTP status rather than supplying an author credential. Existing authenticated GitHub CLI users can also use `gh release download v0.2.0-review-private-20261026 --repo hinsonver/CoRe-Benchmark`.

## Install outside the core and run offline checks

For a fresh core checkout from the downloaded asset:

```sh
unzip "$CORE_DOWNLOAD_DIR/CoRe-review-core-20261026.zip" -d "$CORE_DOWNLOAD_DIR/core"
cd "$CORE_DOWNLOAD_DIR/core"
python3 -m venv .venv
source .venv/bin/activate
pip install -r environment/requirements-replay.txt
python tools/core.py verify
python tools/data.py status
python tools/data.py install \
  --archive "$CORE_DOWNLOAD_DIR/CoRe-submission-VE-M01-M05-historical.zip" \
  --output "$CORE_DOWNLOAD_DIR/history"
```

If using an existing checkout of this fixed tag, run the same installer from its root and keep both the downloaded ZIP and installation outside it. Do not copy or commit the historical ZIP or its extracted files into the core. The unchanged installer verifies the fixed archive hash and all 289 bound files (264 dependencies and 25 scorer/code files), plus the exact `BUNDLE.json` member. It rejects altered, missing, additional or unsafe members and existing or in-repository destinations. Installation does not make network requests or grant redistribution rights.

Before historical validation, prepare your own truthful external local-use JSON record. It must identify your actual `purpose` and `rights_basis`, include `historical_inputs` and `historical_outputs` in `scope`, and set `redistribution` to `false`. Do not use the authors' local-use assertion as proof of reviewer rights or invent a rights basis to satisfy the gate. This record documents local use; it is not a legal ruling or a grant of rights. With your record at `/absolute/local-use.json` (replace this placeholder with its real external path):

```sh
python tools/reproduce_all.py --output build/all-with-history \
  --historical-root "$CORE_DOWNLOAD_DIR/history" \
  --authorization-record /absolute/local-use.json
```

Use a fresh output directory. A completed integrated historical check retains exit 2 for the documented historical limits; exit 1 means an unexpected failure. The core-only route in the [README](../README.md#quick-start) needs neither historical installation nor a local-use record. See the [data guide](data.md), [reproduction guide](reproduction.md) and [coverage matrix](../REPRODUCTION.json) for the distinct scoring routes.

## Access, rights and evidence limits

The repository, Git history and existing Releases were opened for public access on 2026-11-05 at the author's request. Applicable source terms, provider terms and [original notices](../LICENSES.md) still apply; CoRe's code license does not relicense data or archived replies. Public access is not a determination of submission eligibility or a new third-party license.

Hosting the exact archive does not recover the older continuation scoring source, the 12 missing whole-table correction lists or missing historical Rayyan responses and encoding evidence. It does not establish historical model-version availability. The [limitations](limitations.md) and [coverage matrix](../REPRODUCTION.json) retain those boundaries; these downloads make no new model or PubMed calls.

The fixed `v0.2.0` core ZIP keeps its original code and hashes. The current
checkout supplies the updated paper, report, statistical display and
reviewer-owned API entrypoint; see the [inference guide](cluster-inference.md)
and [execution guide](experiment-execution.md). The historical ZIP and its
installation gate remain unchanged. No author API key is included or required;
fresh hosted calls use the reviewer's own credentials.
