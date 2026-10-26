# Original experiment execution: plan and preflight

The packaged statistical replay recomputes published results from frozen responses.
It is not a fresh run of the models. `tools/experiments.py` separately describes and
preflights one original experiment at a time, and contains an explicitly gated
adapter to the retained experiment modules. It does not invent missing model
responses or use public numerical Movies witnesses as model inputs.

No experiment, service call, model download, training or PubMed query was performed
to prepare this entrypoint. The historical hosted versions are not established as
available now. In particular, the frozen decision records that the original Qwen
and DeepSeek APIs could no longer be used. Supplying another endpoint with a
similar model name is not a reproduction and is not authorized by this tool.

## Safe starting commands

Run these from the package root, using Python 3.11. `--plan` is the default.
Both plan and preflight are read-only: they do not import experiment clients,
read response caches, load `.env` files, write run directories or contact services.
Preflight checks local file hashes, Python module availability and environment
variable presence; it never prints credential or endpoint values.

```sh
python3 tools/experiments.py --help
python3 tools/experiments.py --experiment cleaning --dataset hospital --model local:qwen2.5-7b
python3 tools/experiments.py --experiment cleaning --dataset hospital --condition W --construction-seed 2 --model local:qwen2.5-7b --preflight
```

A plan names the exact module/function, arguments, frozen inputs and their hashes,
historical output and hash, and proposed output directory. Preflight returns
`blocked` with concrete missing inputs/software/configuration, or
`ready_to_attempt`. The latter only means local preconditions are present:
`service_status` remains `not_contacted` and historical checkpoint equivalence
remains unverified. Exit codes are 0 for a plan or locally satisfied preflight,
2 for rejected scope/path requests, and 3 for blocked preflight or failed execution.

## Routes and frozen scope

| Experiment | Actual retained route | Required input and setting |
|---|---|---|
| Four-condition cleaning | `src.probe_clean` | Frozen dirty/clean pair; 20-row spread chunks, seed 0, 4096-token initial budget, archived retry handling. Select one condition. |
| Row continuation | `src.probe_rowcont` | Frozen original pair; 50 samples, 10 context rows, seed 0, original 512-token client call with its retained base-model cap. Select clean/dirty, anonymous/named, and optionally dirty error rows. |
| Knowledge conflicts | `src.near_entities.run` | Frozen `data/final/_near/<dataset>/plan.json` and real/near/control pairs; original support levels and standard/evidence prompts. No candidates, screening, reconstruction or new entity selection. |
| Aligned LLM cleaning | `src.aligned.llm` | One frozen condition and copied frozen label indices; 20 labels and original perfect-detection repair prompt; 4096-token budget. |
| Aligned Baran | `src.aligned.baran_chunks` | Same frozen labels/condition; one archived algorithm run seed 0, 1 or 2. |
| Whole-table Baran | `src.e5_baselines` with `--mode perfect` | Frozen condition, 20 sampled labeled tuples, one archived algorithm seed; pretrained value models disabled. |
| TabClean | Explicitly configured external `pipeline`/`main` modules | Frozen archived TabClean input pair, not a substituted audit table; original DeepSeek backbone and development split; separate pinned upstream checkout. Currently blocked by historical hosted-version availability. |
| Rayyan reference retrieval | `src.rayyan_audit.pubmed` and `judge` | The accepted, hash-bound 279-cell sample and original title-matching/judgment rules; no new sampling and no original audit replacement. Future retrieval needs explicit network authorization. |

Cleaning supports Hospital and Movies F/W/S construction seeds 0, 1 and 2, plus
their original condition. Beers has construction seed 0 only; Rayyan has no
four-condition experiment. Whole-table Baran is limited to archived condition/run
combinations. Its algorithm seeds do **not** create new construction seeds, so the
archived three Baran runs on Beers remain distinct from forbidden Beers table
extensions. Aligned conditions use the archived base construction and fixed label
files; labels are not silently redrawn.

The eight main cleaners retain their exact historical `provider:model` identifiers.
Continuation additionally permits the archived OLMo instruction/base identifiers,
but not new OLMo cleaning experiments. Continuation datasets are Hospital, Flights,
Beers, Rayyan, Movies (`movies_1`) and Tax, subject to actual archived coverage.
The planner requires an exact archived output filename in
`data/manifests/CORE_SOURCES.json`; a model in the archive does not authorize every
dataset/condition/continuation setting. The retained base OLMo files use the
historical `localbase__olmo2-7b` filename prefix despite recording the full model
identifier in their metadata; the adapter accounts for that naming exception.

Examples for each additional family (all remain preflight only):

```sh
python3 tools/experiments.py --experiment continuation --dataset flights --model local:qwen2.5-7b --source dirty --error-rows --preflight
python3 tools/experiments.py --experiment conflicts --dataset hospital --model local:qwen2.5-7b --preflight
python3 tools/experiments.py --experiment aligned-llm --dataset hospital --condition F --model custom:deepseek/deepseek-v4-pro --preflight
python3 tools/experiments.py --experiment aligned-baran --dataset hospital --condition F --algorithm-seed 2 --preflight
python3 tools/experiments.py --experiment baran --dataset beers --condition S --algorithm-seed 2 --preflight
python3 tools/experiments.py --experiment tabclean --dataset rayyan --model custom:deepseek/deepseek-v4-pro --preflight
python3 tools/experiments.py --experiment rayyan-retrieval --dataset rayyan --preflight
```

## Inputs, services and software

Public Hospital/Beers inputs are included with frozen hashes. Movies row inputs
remain outside the distributable package. To preflight an authorized Movies run,
supply both `--private-root /absolute/external/history` and
`--authorization-record /absolute/author-supplied-record.json`. The existing
historical validation gate checks the entire private dependency hash list and a
rights record containing nonempty `purpose` and `rights_basis`, scope entries
`historical_inputs` and `historical_outputs`, and `redistribution: false`.
This records an author's asserted basis, not a legal adjudication or new sharing
permission. No default private path, historical fallback or authorization is
inferred. Movies conflicts explicitly bind the module's read-only input directory
to that validated external history, because the historical function reads its
CSV files directly rather than through `data.load`.

Client dependencies are listed in
[`requirements-experiments.txt`](../environment/requirements-experiments.txt).
Use the Python interpreter of the intended execution environment for preflight;
its installed modules are what get checked. The offline tested runtime is not
proof that optional model serving or baseline software is installed.

The historical whole-table/aligned Baran environment used `raha==1.26`. Raha is
not bundled; use an isolated baseline environment with that version and its
dependency metadata, then run this same tool with that environment's interpreter.
Its transitive dependencies include NumPy, pandas, SciPy, scikit-learn, Matplotlib,
prettytable, mwparserfromhell, beautifulsoup4 and py7zr. A module-presence check is
not a guarantee of binary compatibility; preserve a resolved environment record
for any future actual run. No baseline software is installed by this entrypoint.

TabClean source is not vendored in this candidate. `code/scripts/run_tabclean.py`
is retained as historical source, but is **not** an executable shortcut: it has
hard-coded source/output paths and a `.env` reader. The historical upstream
`config.py` also reads a parent `.env`. The new adapter supplies the complete
archived configuration in memory before importing upstream pipeline/main, rather
than importing that configuration file. It retains all five agent models as
DeepSeek-V4-Pro, ten maximum iterations, 0.95 development F1 threshold, three-step
early stopping, the historical temperature argument and disabled thinking. It
preserves the archived relay cost-tracker compatibility wrapper. An external
checkout must be supplied with `--tabclean-root`; its requirements historically
included pandas, langchain-openai, langgraph and python-dateutil. Generated-code
execution in TabClean is not sandboxed: use an isolated environment with no
unrelated credentials or mounted sensitive data. No external checkout or hosted
version is declared usable merely because files or environment variables exist.
The author-side historical checkout was identified at commit
`ae292b6ff8118c8786cd7c97364e9a8a07f00b62`. Preflight requires the supplied path
to be its own Git checkout at exactly that commit, verifies a clean tracked tree
against the pinned commit, requires the complete tracked files and the
executor/skills/error-type support files, and compares **every tracked regular
file** byte-for-byte with its raw pinned Git blob. It does not use worktree
`git diff`, which can execute repository-configured clean filters even when
external-diff and textconv are disabled. Raw `cat-file blob` reads do not apply
filters; Git replacement objects and lazy fetching are disabled.
It rejects untracked importable source/native modules even when ignored by Git.
Object-level Git reads do not fetch or import upstream Python. Existing ordinary
`__pycache__` entries are bypassed with a new run-local `PYTHONPYCACHEPREFIX`;
sourceless untracked bytecode outside those cache directories is rejected.
`tabclean_source_verified: true` therefore verifies the local source gate, not
historical API availability, baseline dependencies, a complete successful run or
the scientific equivalence of new responses.

Local instruction/base clients require an already running compatible service and
`LOCAL_BASE_URL`, optionally `LOCAL_API_KEY`; a URL is configuration, not evidence
that the checkpoint or service is available. Historical model repository names,
tensor parallelism, context lengths and serving scripts are retained under
`code/scripts/server/`. These scripts are archival and include out-of-scope model
rows and download commands; do not execute the whole model list. No GPU, weights,
checkpoint revision or serving environment is provided by the client dependency
file. The relevant selected checkpoint must already exist and match the historical
configuration. The planner never starts a server or downloads weights.

Hosted `openai` uses `OPENAI_API_KEY`; archived relay runs use `CUSTOM_BASE_URL`
and `CUSTOM_API_KEY`. Environment presence is reported only as true/false.
Hosted runs remain blocked because historical endpoint/version availability has
not been established; cost acknowledgement does not bypass that blocker.

## Explicit future execution and output isolation

Actual model execution is outside this preparation task and the frozen manuscript
does not authorize new runs. If the author later explicitly authorizes a permitted
historical rerun and its network/data transfer, the same command may add both
`--execute --allow-network`, and hosted runs additionally require
`--allow-paid-api`. These flags acknowledge risks; they do not grant dataset rights,
unfreeze experiments, override missing software, or authorize model substitutions.

Every attempt requires a **new**, non-symlink directory below
`build/experiment-runs/`, generated automatically or selected by `--output-dir`.
Existing directories are refused; there is no implicit cache reuse/resume. All
output overrides and the empty new response-cache path are set before importing
the real modules. The adapter never runs the intentionally disabled
`src.pipeline`, writes original archives, rebuilds frozen tables, or replaces
frozen labels. A run records `execution.json`, `execution.log`, separate generated
outputs and any new cache/usage records. `CORE_*` variables inherited from another
workflow cannot redirect this run. Authorized Movies outputs remain private work
files under `build/`; they are not permission to redistribute movie records.

The new process's successful exit is not scientific acceptance, a newly accepted
paper result or proof of the old remote model version. New sampled GPT outputs
need not be byte-identical. Use frozen statistical replay for the accepted paper's
numbers, and keep future reruns separate until an explicitly authorized scientific
comparison and change-control review are complete.

The Rayyan retrieval route keeps the accepted 279 sampled cells and their strata,
population weights, title queries and original title-similarity threshold. It
does not run the archival `main()` default 30-per-stratum sampler. A future
explicit retrieval writes `rayyan-retrieval.json` and
`pubmed-retrieved-records.json` only in its new run directory. PubMed may change;
new responses are separate work products, not a replacement for the frozen audit
or a new accepted estimate. No PubMed query is needed for public statistical
replay or this route's plan/preflight.
