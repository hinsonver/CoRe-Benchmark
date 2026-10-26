# Download the fixed private GitHub delivery

The current delivery is the [2026-10-26 private prerelease](https://github.com/hinsonver/CoRe-Benchmark/releases/tag/v0.2.0-review-private-20261026) in the existing `hinsonver/CoRe-Benchmark` repository. It has three assets:

| Asset | Purpose |
| --- | --- |
| `CoRe-review-core-20261026.zip` | Current four-author paper, 22-page technical report, code, non-Movies raw evidence and numerical Movies witnesses; no raw Movies records or replies |
| `CoRe-submission-VE-M01-M05-historical.zip` | Exact historical Movies inputs, archived replies and bound historical code, separate from the Git tree and statistical core |
| `SHA256SUMS` | SHA-256 checksums of both ZIP assets |

The [previous fixed private release](https://github.com/hinsonver/CoRe-Benchmark/releases/tag/v0.1.0-a04-review-private-20261022), tag and assets are unchanged. Use the fixed tag above, not a moving `latest` URL or a source-code ZIP offered automatically by GitHub.

## Authenticate and download

Use the GitHub CLI with an account that actually has access to the private repository. If already signed in to the correct account, inspect its status instead of signing in again. Never paste a token into a command or commit credentials:

```sh
gh auth login --hostname github.com
gh auth status --hostname github.com
CORE_DOWNLOAD_DIR="$(mktemp -d)"
gh release download v0.2.0-review-private-20261026 \
  --repo hinsonver/CoRe-Benchmark \
  --pattern CoRe-review-core-20261026.zip \
  --pattern CoRe-submission-VE-M01-M05-historical.zip \
  --pattern SHA256SUMS \
  --dir "$CORE_DOWNLOAD_DIR"
(cd "$CORE_DOWNLOAD_DIR" && shasum -a 256 -c SHA256SUMS)
```

The temporary download directory is outside the repository. Stop if either checksum fails. The historical ZIP's fixed SHA-256 is `9569fe9d6d475ea0243b5d9a04f2a8ed098557873ffca7597cbcb6eef67bbc09`.

Its stable asset URL is [the historical ZIP](https://github.com/hinsonver/CoRe-Benchmark/releases/download/v0.2.0-review-private-20261026/CoRe-submission-VE-M01-M05-historical.zip). A browser must be signed in to an account with repository access. An unauthenticated request may return 404; that is not evidence that the asset is publicly accessible or absent. The authenticated CLI command above handles private Release downloads without putting a credential in the URL.

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

Private hosting does not establish that a particular reviewer can access the repository, submission eligibility, public availability or third-party redistribution rights. No public release or change of repository visibility is implied. Applicable source terms, provider terms and [original notices](../LICENSES.md) still apply; CoRe's code license does not relicense data or archived replies. Any public publication or wider sharing requires separate approval and the relevant rights.

Hosting the exact archive does not recover the older continuation scoring source, the 12 missing whole-table correction lists or missing historical Rayyan responses and encoding evidence. It does not establish that the original Qwen and DeepSeek APIs remain available. The [limitations](limitations.md) and [coverage matrix](../REPRODUCTION.json) retain those boundaries; these downloads make no new model or PubMed calls.
