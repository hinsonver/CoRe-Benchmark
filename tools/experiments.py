"""Plan or preflight one archived experiment; execution is explicit and isolated.

This preparation entrypoint uses only the standard library. It never imports a
model client, reads response caches, loads .env files, or contacts a service in
plan/preflight mode. It does not invoke the deliberately disabled pipeline.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
TABCLEAN_COMMIT = "ae292b6ff8118c8786cd7c97364e9a8a07f00b62"
ROUTES = ("cleaning", "continuation", "conflicts", "aligned-llm", "aligned-baran", "baran", "tabclean", "rayyan-retrieval")
MODELS = {
    "custom:deepseek/deepseek-v4-pro", "custom:qwen/qwen3.8-max",
    "custom:z-ai/glm-5.3", "openai:gpt-6.1-sol", "local:qwen2.5-7b",
    "local:llama3.1-8b", "local:qwen2.5-14b", "local:qwen2.5-32b-awq",
    "local:olmo2-7b", "local:mlx-community/OLMo-2-1124-7B-Instruct-4bit",
    "localbase:allenai/OLMo-2-1124-7B",
}
SUFFIX = {"O": "", "F": "_fresh", "W": "_surrogatewords", "S": "_surrogate"}
OVERRIDES = {
    "CORE_BUILD_DIR": "work", "CORE_CACHE_FILE": "cache/responses.jsonl",
    "CORE_P1_DIR": "continuation", "CORE_P2_DIR": "cleaning", "CORE_NEAR_DIR": "conflicts",
    "CORE_ALIGNED_DIR": "aligned", "CORE_E4_DIR": "tabclean", "CORE_E5_DIR": "baran",
}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    action = p.add_mutually_exclusive_group()
    action.add_argument("--plan", action="store_true", help="print a read-only plan (the default)")
    action.add_argument("--preflight", action="store_true", help="check local inputs/configuration, without service calls")
    action.add_argument("--execute", action="store_true", help="explicitly attempt this one archived experiment")
    p.add_argument("--experiment", choices=ROUTES, required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--condition", choices=SUFFIX, default="O")
    p.add_argument("--construction-seed", type=int, default=0)
    p.add_argument("--algorithm-seed", type=int, default=0, help="Baran random seed, not a construction seed")
    p.add_argument("--model", help="exact archived provider:model identifier; not needed for Baran")
    p.add_argument("--source", choices=("clean", "dirty"), default="clean", help="continuation source")
    p.add_argument("--named", action="store_true", help="continuation with dataset name")
    p.add_argument("--error-rows", action="store_true", help="continuation dirty contexts with error rows")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--output-dir", help="new directory below build/experiment-runs; never reused")
    p.add_argument("--private-root", help="explicit external historical Movies tree")
    p.add_argument("--authorization-record", help="author-supplied historical-input/output rights record")
    p.add_argument("--tabclean-root", help="explicit externally installed pinned TabClean checkout")
    p.add_argument("--allow-network", action="store_true", help="acknowledge endpoint/data-transfer risk for execution")
    p.add_argument("--allow-paid-api", action="store_true", help="additional acknowledgement of hosted API costs")
    return p


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_output(value, root):
    root = Path(root).resolve()
    base = root / "build/experiment-runs"
    candidate = Path(value) if value else base / ("run-" + uuid.uuid4().hex)
    if not candidate.is_absolute():
        candidate = root / candidate
    # Check the original path components before resolve hides a symlink.
    if any(p.is_symlink() for p in (candidate, *candidate.parents)):
        raise ValueError("output path must not contain symlinks")
    candidate = candidate.resolve()
    if base not in candidate.parents or candidate.exists():
        raise ValueError("output must be a new directory below build/experiment-runs")
    return candidate


def make_plan(a, root=ROOT):
    root = Path(root).resolve()
    if a.workers < 1 or a.workers > 16:
        raise ValueError("workers must be between 1 and 16")
    if a.construction_seed not in (0, 1, 2):
        raise ValueError("construction seed is outside frozen scope")
    if a.algorithm_seed not in (0, 1, 2):
        raise ValueError("algorithm seed is outside archived Baran scope")
    continuation = a.experiment == "continuation"
    retrieval = a.experiment == "rayyan-retrieval"
    if a.dataset not in (("hospital", "flights", "beers", "rayyan", "movies_1", "tax") if continuation
                         else ("rayyan",) if retrieval
                         else (("hospital", "movies", "beers", "rayyan") if a.experiment == "tabclean"
                               else ("hospital", "movies", "beers"))):
        raise ValueError("dataset is outside this experiment's frozen scope")
    if a.condition == "O" and a.construction_seed or a.dataset in ("beers", "rayyan") and a.construction_seed:
        raise ValueError("construction seed must remain 0 for original tables and Beers/Rayyan")
    if a.experiment not in ("cleaning", "baran") and (a.construction_seed or a.condition != "O"):
        if a.experiment not in ("aligned-llm", "aligned-baran", "tabclean") or a.construction_seed:
            raise ValueError("condition/construction selection is unsupported for this experiment")
    if a.dataset == "rayyan" and a.condition != "O":
        raise ValueError("Rayyan has no constructed conditions")
    if not continuation and (a.named or a.error_rows or a.source != "clean"):
        raise ValueError("continuation options cannot change another experiment")
    if a.error_rows and a.source != "dirty":
        raise ValueError("error-row continuation requires dirty source")
    if a.experiment not in ("baran", "aligned-baran") and a.algorithm_seed:
        raise ValueError("algorithm seed applies only to Baran")
    needs_model = a.experiment not in ("baran", "aligned-baran", "rayyan-retrieval")
    if needs_model and a.model not in MODELS:
        raise ValueError("model must be an exact archived identifier, not a substitute")
    if needs_model and not continuation and "olmo" in a.model.lower():
        raise ValueError("OLMo auxiliary models are restricted to the continuation experiment")
    if a.experiment == "tabclean" and a.model != "custom:deepseek/deepseek-v4-pro":
        raise ValueError("TabClean's frozen backbone is DeepSeek-V4-Pro")
    if not needs_model and a.model:
        # A caller may share a model option across plans; it has no baseline effect.
        if a.model not in MODELS:
            raise ValueError("unsupported model")
    tag = (a.model or "").replace(":", "_").replace("/", "_")
    if a.model == "localbase:allenai/OLMo-2-1124-7B":
        tag = "localbase__olmo2-7b"  # Historical filename differs from the recorded model spec.
    table = a.dataset + SUFFIX[a.condition]
    if a.dataset == "beers" and a.condition == "O" and not continuation:
        table = "beers_orig"
    if a.construction_seed:
        table += "_s" + str(a.construction_seed)
    prefix = "artifacts/raw_outputs/"
    entrypoint = "main"
    if retrieval:
        module, entrypoint = "src.rayyan_audit", "pubmed/judge on frozen sample"
        historical = "results/derived/rayyan_audit.json"
        invocation = {"sample": historical, "resample": False}
    elif a.experiment == "cleaning":
        module = "src.probe_clean"
        historical = f"{prefix}p2/{tag}__{table}__k20__spread.json"
        invocation = ["--model", a.model, "--dataset", table, "--spread", "--workers", str(a.workers),
                      "--max-tokens", "4096"]
    elif continuation:
        module = "src.probe_rowcont"
        historical = f"{prefix}p1/{tag}__{table}__{a.source}__{'named' if a.named else 'anon'}{'__err' if a.error_rows else ''}.json"
        invocation = ["--model", a.model, "--dataset", table, "--source", a.source, "--n", "50", "--k", "10", "--seed", "0"]
        invocation += (["--named"] if a.named else []) + (["--error-rows"] if a.error_rows else [])
    elif a.experiment == "conflicts":
        module, entrypoint = "src.near_entities", "run"
        historical = f"{prefix}near/{tag}__{a.dataset}.json"
        invocation = {"dataset": a.dataset, "model": a.model, "workers": a.workers, "max_tokens": 4096}
    elif a.experiment.startswith("aligned-"):
        module = "src.aligned"
        entrypoint = "llm" if a.experiment == "aligned-llm" else "baran_chunks"
        historical = f"{prefix}aligned/{tag}__{table}.json" if entrypoint == "llm" else f"{prefix}aligned/baran__{table}__run{a.algorithm_seed}.json"
        invocation = {"base": a.dataset, "condition": table, "model": a.model,
                      "workers": a.workers, "run": a.algorithm_seed}
    elif a.experiment == "baran":
        module = "src.e5_baselines"
        historical = f"{prefix}e5/{table}__perfect__seed{a.algorithm_seed}.json"
        invocation = ["--dataset", table, "--mode", "perfect", "--seeds", str(a.algorithm_seed)]
    else:
        module, entrypoint = "TabClean.pipeline", "configured-upstream"
        historical = f"{prefix}e4/tabclean/{table}/final_cleaned.csv"
        invocation = {"model": "deepseek/deepseek-v4-pro", "table": table}
    sources = json.loads((root / "data/manifests/CORE_SOURCES.json").read_text())
    originals = sources["original_files"]
    if historical not in originals:
        raise ValueError("requested model/dataset/condition combination has no archived run")
    output = safe_output(a.output_dir, root)
    copies = []
    if a.experiment.startswith("aligned-"):
        copies.append([f"{prefix}aligned/labels_{a.dataset}.json", f"aligned/labels_{a.dataset}.json"])
    if retrieval:
        inputs = [historical]
    elif a.experiment == "conflicts":
        inputs = [f"data/final/_near/{a.dataset}/plan.json"]
        inputs += [f"data/final/_near/{a.dataset}/{typ}/{name}.csv" for typ in ("real", "near", "control") for name in ("dirty", "clean")]
    elif a.experiment == "tabclean":
        inputs = [f"{prefix}e4/inputs/{table}/{name}.csv" for name in ("dirty", "clean")]
    else:
        inputs = [f"data/final/{table}/{name}.csv" for name in ("dirty", "clean")]
    inputs += [x[0] for x in copies]
    for relative in inputs:
        if relative not in originals:
            raise ValueError("required input lacks frozen hash binding: " + relative)
    dependencies = ["pandas", "numpy"]
    if needs_model:
        dependencies.append("openai")
    if a.experiment in ("baran", "aligned-baran"):
        dependencies.append("raha")
    if a.experiment == "tabclean":
        dependencies += ["langchain_openai", "langgraph", "dateutil"]
    private = any(relative in sources["private_files"] for relative in inputs)
    return {"schema_version": 1, "action": "execute" if a.execute else "preflight" if a.preflight else "plan",
            "experiment": a.experiment, "module": module, "entrypoint": entrypoint, "invocation": invocation,
            "model": a.model if needs_model else None, "dataset": a.dataset, "table": table,
            "construction_seed": a.construction_seed, "algorithm_seed": a.algorithm_seed,
            "historical_output": historical, "historical_output_sha256": originals[historical],
            "output_directory": str(output), "required_inputs": inputs,
            "input_hashes": {n: originals[n] for n in inputs}, "copy_inputs": copies,
            "dependencies": dependencies, "requires_authorized_history": private,
            "environment_overrides": {k: str(output / v) for k, v in OVERRIDES.items()},
            "network_used": False, "response_cache_read": False,
            "notice": "New runs cannot promise historical model availability or byte-identical sampled outputs; frozen evidence is never replaced."}


def verify_tabclean_checkout(upstream):
    """Read-only pin/working-tree verification; never imports upstream code.

    Only object-level Git reads are used: worktree diff can execute configured
    clean filters, even with external-diff and textconv disabled. Every tracked
    regular file is compared with its raw pinned blob without filter conversion.
    Untracked sources include ignored paths; legitimate __pycache__ entries are
    bypassed using an isolated PYTHONPYCACHEPREFIX in the execution subprocess.
    """
    upstream = Path(upstream).resolve()
    if not upstream.is_dir():
        return ["pinned TabClean upstream checkout is unavailable; no download is performed"]
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_NO_LAZY_FETCH": "1", "LC_ALL": "C"})
    prefix = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(upstream)]
    def git(*args):
        result = subprocess.run([*prefix, *args], env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=30)
        if result.returncode:
            raise ValueError("Git command failed")
        return result.stdout
    try:
        top = Path(os.fsdecode(git("rev-parse", "--show-toplevel")).strip()).resolve()
        if top != upstream:
            return ["TabClean path is not its own Git checkout"]
        head = os.fsdecode(git("rev-parse", "HEAD")).strip()
        if head != TABCLEAN_COMMIT:
            return ["TabClean commit differs from required pinned commit " + TABCLEAN_COMMIT]
        records = git("ls-tree", "-r", "-z", TABCLEAN_COMMIT).split(b"\0")
        tracked = {}
        for record in records:
            if not record:
                continue
            info, name = record.split(b"\t", 1)
            mode, kind, object_id = info.split()
            relative = Path(os.fsdecode(name))
            if relative.is_absolute() or ".." in relative.parts or mode not in (b"100644", b"100755") or kind != b"blob":
                return ["TabClean pinned tree contains an unsupported source member"]
            tracked[relative.as_posix()] = object_id.decode("ascii")
            path = upstream / relative
            if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
                return ["TabClean tracked source/support file is missing or unsafe: " + relative.as_posix()]
        required = {"main.py", "pipeline.py", "config.py", "executor.py", "skills.md", "error_types.txt", "requirements.txt"}
        if not required <= tracked.keys():
            return ["TabClean required source/support files are missing from pinned tree"]
        for name, expected in tracked.items():
            # cat-file's raw blob mode never applies attributes, clean filters,
            # textconv, smudge filters or index assume-unchanged shortcuts.
            if (upstream / name).read_bytes() != git("cat-file", "blob", expected):
                return ["TabClean dirty tracked file blob differs from pinned tree: " + name]
        # Without exclude-standard, ls-files also enumerates ignored local files.
        for name in git("ls-files", "--others", "-z").split(b"\0"):
            if not name:
                continue
            relative = Path(os.fsdecode(name))
            suffix = relative.suffix.lower()
            if suffix in (".py", ".pyw", ".so", ".pyd", ".dll", ".pth") or (
                    suffix in (".pyc", ".pyo") and "__pycache__" not in relative.parts):
                return ["TabClean untracked importable source is forbidden: " + relative.as_posix()]
        return []
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        return ["TabClean Git checkout could not be verified without source execution"]


def preflight(plan, a, root=ROOT):
    root = Path(root).resolve()
    safe_output(plan["output_directory"], root)
    blockers = []
    missing = [name for name in plan["dependencies"] if importlib.util.find_spec(name) is None]
    blockers += ["missing execution dependency: " + name for name in missing]
    resolved = {}
    private_ok = False
    if plan["requires_authorized_history"]:
        if not a.private_root or not a.authorization_record:
            blockers.append("explicit private root and authorization record are required for historical Movies inputs")
        else:
            # Runtime is standard-library-only; do not import any experiment/client.
            from types import SimpleNamespace
            filename = root / "code/src/core_runtime.py"
            namespace = {"__file__": str(filename)}
            exec(compile(filename.read_text(), str(filename), "exec"), namespace)
            runtime = SimpleNamespace(**namespace)
            try:
                runtime.preflight_private(root, a.private_root, a.authorization_record)
                private_ok = True
            except (ValueError, OSError, KeyError, TypeError) as error:
                blockers.append("historical authorization/hash preflight failed: " + type(error).__name__)
    sources = json.loads((root / "data/manifests/CORE_SOURCES.json").read_text())
    for relative in plan["required_inputs"]:
        private = relative in sources["private_files"]
        if private and not private_ok:
            continue
        path = (Path(a.private_root).resolve() if private else root) / relative
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
            blockers.append("missing/unsafe frozen input: " + relative)
        elif sha(path) != plan["input_hashes"][relative]:
            blockers.append("frozen input hash differs: " + relative)
        else:
            resolved[relative] = str(path)
    required_env = []
    if plan["model"]:
        provider = plan["model"].split(":", 1)[0]
        required_env = ["LOCAL_BASE_URL"] if provider in ("local", "localbase") else ["OPENAI_API_KEY"] if provider == "openai" else ["CUSTOM_BASE_URL", "CUSTOM_API_KEY"]
        absent = [key for key in required_env if not os.environ.get(key)]
        blockers += ["missing environment variable: " + key for key in absent]
        if provider not in ("local", "localbase"):
            blockers.append("historical hosted endpoint/version availability is not established; no replacement is authorized")
    upstream = None
    tabclean_verified = False
    if plan["experiment"] == "tabclean":
        upstream = Path(a.tabclean_root).resolve() if a.tabclean_root else root / "code/third_party/TabClean"
        source_blockers = verify_tabclean_checkout(upstream)
        blockers.extend(source_blockers)
        tabclean_verified = not source_blockers
        # The historical hosted backbone is unavailable regardless of checkout presence.
    return {"status": "blocked" if blockers else "ready_to_attempt", "blockers": blockers,
            "dependencies_missing": missing, "required_environment": required_env,
            "environment_present": {key: bool(os.environ.get(key)) for key in required_env},
            "service_status": "not_contacted", "network_used": False, "response_cache_read": False,
            "resolved_inputs": resolved, "tabclean_root": str(upstream) if upstream else None,
            "tabclean_source_verified": tabclean_verified,
            "tabclean_required_commit": TABCLEAN_COMMIT if upstream else None,
            "historical_versions_reverified": False, "private_inputs_verified": private_ok}


# This adapter is evaluated only in a fresh subprocess after all execution gates.
# Setting environment variables before imports is essential: the archived modules
# bind output directories and load their response cache at import time.
WORKER = r'''
import importlib, json, os, runpy, sys
from pathlib import Path
p=json.loads(sys.argv[1]); f=json.loads(sys.argv[2])
route=p["experiment"]
if route == "rayyan-retrieval":
    # Keep the accepted sample cells/strata; never invoke main(), whose default
    # sample size and hard-coded output path differ from this bound archive.
    m=importlib.import_module(p["module"])
    sample=json.loads(Path(f["resolved_inputs"][p["invocation"]["sample"]]).read_text())
    cache={}; rows=[]
    for original in sample:
        row={key:original[key] for key in ("stratum","row","col","dirty","clean","title","population")}
        title=row["title"]
        if title not in cache:
            try: cache[title]=m.pubmed(title)
            except RuntimeError: cache[title]=None
        rec=cache[title]; row["pmid"]=rec.get("uid") if rec else None
        if rec:
            row.update(m.judge(row["stratum"],row["col"],row["dirty"],row["clean"],rec))
        rows.append(row)
    out=Path(p["output_directory"])/"rayyan-retrieval.json"
    out.write_text(json.dumps(rows,ensure_ascii=False,indent=1)+"\n")
    (out.parent/"pubmed-retrieved-records.json").write_text(json.dumps(cache,ensure_ascii=False,indent=1)+"\n")
    m.summary(rows)
elif route in ("cleaning", "continuation", "baran"):
    sys.argv=[p["module"], *p["invocation"]]
    runpy.run_module(p["module"], run_name="__main__")
elif route == "conflicts":
    m=importlib.import_module(p["module"])
    if p["requires_authorized_history"]:
        m.NEAR=Path(f["resolved_inputs"]["data/final/_near/movies/plan.json"]).parent.parent
    v=p["invocation"]
    m.run(v["dataset"], v["model"], v["workers"], v["max_tokens"])
elif route in ("aligned-llm", "aligned-baran"):
    m=importlib.import_module(p["module"]); v=p["invocation"]
    if route == "aligned-llm":
        m.llm(v["base"], v["model"], workers=v["workers"], max_tokens=4096, only=[v["condition"]])
    else:
        m.baran_chunks(v["base"], run=v["run"], only=[v["condition"]])
else:
    # Equivalent configuration to the archived adapter, without its hard-coded
    # .env loader/output directory. TabClean can execute generated Python code;
    # this is not a sandbox. Never run with unrelated secrets in the environment.
    upstream=Path(f["tabclean_root"]); work=Path(p["output_directory"])/"tabclean"/p["table"]
    work.mkdir(parents=True)
    key=os.environ.pop("CUSTOM_API_KEY"); endpoint=os.environ.pop("CUSTOM_BASE_URL")
    for name in list(os.environ):
        if name.endswith(("_API_KEY", "_TOKEN", "_SECRET")):
            os.environ.pop(name, None)
    for name,folder in (("TABCLEAN_WORK_DIR",work),("TABCLEAN_RESULTS_DIR",work/"results"),("TABCLEAN_PRIVATE_DIR",work/"private")):
        os.environ[name]=str(folder)
    sys.path.insert(0,str(upstream))
    # Historical config.py itself reads ../.env. Supply its complete experiment
    # configuration without importing that file, rather than triggering a
    # credential read. These constants match the retained historical checkout.
    from types import ModuleType
    config=ModuleType("config")
    config.BASE_DIR=upstream; config.PROJECT_DIR=upstream.parent
    config.DEFAULT_PRIVATE_DIR=work/"private"; config.OPENAI_API_KEY=""
    config.PRIVATE_DATA_DIR=work/"private"; config.DATASETS_DIR=upstream/"datasets"
    config.RESULTS_DIR=work/"results"; config.WORK_DIR=str(work)
    config.SKILLS_PATH=str(upstream/"skills.md"); config.ERROR_TYPES_PATH=str(upstream/"error_types.txt")
    config.MAX_ITERATIONS=10; config.F1_THRESHOLD=0.95; config.EARLY_STOP_PATIENCE=3
    for name in ("MODEL_DIAGNOSE","MODEL_REVIEW","MODEL_STRATEGIZE","MODEL_CODE","MODEL_DEBUGGER"):
        setattr(config,name,p["invocation"]["model"])
    sys.modules["config"]=config
    pipeline=importlib.import_module("pipeline")
    from langchain_openai import ChatOpenAI
    def make_llm(model, temperature=0.7):
        return ChatOpenAI(model=model,api_key=key,base_url=endpoint,temperature=temperature,
                          extra_body={"thinking":{"type":"disabled"}},timeout=600)
    pipeline._make_llm=make_llm
    record=pipeline.cost_tracker.record
    def safe_record(*args,**kwargs):
        try: return record(*args,**kwargs)
        except TypeError: return None
    pipeline.cost_tracker.record=safe_record
    main=importlib.import_module("main"); main.WORK_DIR=str(work)
    table=p["table"]; prefix="artifacts/raw_outputs/e4/inputs/"+table+"/"
    sys.argv=["main.py","--csv",f["resolved_inputs"][prefix+"dirty.csv"],"--gt",f["resolved_inputs"][prefix+"clean.csv"]]
    os.chdir(work); main.main()
'''


def execute(plan, a, root=ROOT):
    check = preflight(plan, a, root)
    blockers = list(check["blockers"])
    if not a.execute:
        blockers.append("execution requires --execute")
    if not a.allow_network:
        blockers.append("execution requires --allow-network; this is not service verification")
    if plan["model"] and not plan["model"].startswith(("local:", "localbase:")) and not a.allow_paid_api:
        blockers.append("hosted execution additionally requires --allow-paid-api")
    if blockers:
        return {**check, "status": "blocked", "blockers": blockers}
    output = safe_output(plan["output_directory"], root)
    # Revalidate immediately before claiming the directory. Existing runs are
    # never resumed: cache/output reuse needs a separate explicitly reviewed tool.
    output.mkdir(parents=True, exist_ok=False)
    # The archived hosted client logs usage before its later cache mkdir.
    # Prepare only the new cache parent, never an existing historical cache.
    Path(plan["environment_overrides"]["CORE_CACHE_FILE"]).parent.mkdir()
    for relative, destination in plan["copy_inputs"]:
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(check["resolved_inputs"][relative], target)
    env = {k: v for k, v in os.environ.items() if not k.startswith("CORE_")}
    env.update(plan["environment_overrides"])
    env.update({"CORE_ARTIFACT_ROOT": str(Path(root).resolve()), "CORE_MODE": "public",
                "PYTHONPATH": str(Path(root).resolve() / "code"), "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": str(output / "python-cache")})
    if plan["requires_authorized_history"]:
        env.update({"CORE_MODE": "authorized", "CORE_PRIVATE_ROOT": str(Path(a.private_root).resolve()),
                    "CORE_AUTHORIZATION_RECORD": str(Path(a.authorization_record).resolve())})
    # Avoid emitting endpoint URLs or credentials in either the plan or process
    # metadata; only the child inherits the selected provider configuration.
    metadata = {"plan": plan, "preflight": check}
    (output / "execution.json").write_text(json.dumps(metadata, indent=2) + "\n")
    with (output / "execution.log").open("x") as log:
        result = subprocess.run([sys.executable, "-B", "-c", WORKER, json.dumps(plan), json.dumps(check)],
                                cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT)
    return {"status": "finished" if result.returncode == 0 else "failed", "returncode": result.returncode,
            "output_directory": str(output), "frozen_outputs_replaced": False,
            "notice": "A successful process exit is not scientific acceptance or proof of historical version equivalence."}


def main(argv=None):
    p = parser()
    a = p.parse_args(argv)
    try:
        plan = make_plan(a)
        result = execute(plan, a) if a.execute else preflight(plan, a) if a.preflight else plan
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "rejected", "reason": str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return 3 if result.get("status") in ("blocked", "failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
