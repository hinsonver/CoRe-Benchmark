"""Run every CoRe experiment for one model: P2 four conditions per dataset, the near-entity
condition, and (optionally) P1. Meant for a vLLM server (model spec "local:<served name>"), but
works with any spec; answers are cached, so a crashed run resumes where it stopped.

Usage:
  LOCAL_BASE_URL=http://127.0.0.1:8000/v1 .venv/bin/python -m src.pipeline --model local:qwen2.5-7b \
      --workers 16 [--max-tokens 1500] [--datasets hospital movies beers] [--no-near] [--p1] [--seeds 1 2]
Logs: results/logs/pipeline__<model>.log (the P2 comparison tables and near-entity summaries).
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime

from .data import BUILD, ROOT

CONDITIONS = {
    "hospital": ["hospital", "hospital_fresh", "hospital_surrogatewords", "hospital_surrogate"],
    "movies": ["movies", "movies_fresh", "movies_surrogatewords", "movies_surrogate"],
    "beers": ["beers_orig", "beers_fresh", "beers_surrogatewords", "beers_surrogate"],
}
NEAR = ["hospital", "beers", "movies"]
SEEDED = ["hospital", "movies"]   # bases whose fresh and surrogate tables exist for other seeds (<name>_sN)


def step(log, title: str, args: list[str]) -> int:
    """Run one experiment CLI, streaming its output into the log."""
    stamp = datetime.now().strftime("%m-%d %H:%M:%S")
    log.write(f"\n===== [{stamp}] {title}\n$ {' '.join(args)}\n")
    log.flush()
    rc = subprocess.run([sys.executable, "-m", *args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
    log.write(f"----- exit {rc}\n")
    log.flush()
    return rc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--datasets", nargs="*", default=list(CONDITIONS))
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--no-near", action="store_true")
    ap.add_argument("--seeds", nargs="*", type=int, default=[],
                    help="also run P2 on the fresh and surrogate tables of these construction seeds")
    ap.add_argument("--p1", action="store_true", help="also run P1 row continuation (clean + dirty, anonymous and named, error rows)")
    ap.add_argument("--p1-datasets", nargs="+", default=["hospital", "flights", "beers", "rayyan", "movies_1", "tax"])
    ap.add_argument("--p1-n", type=int, default=50)
    a = ap.parse_args()
    tag = a.model.replace(":", "_").replace("/", "_")
    log_dir = BUILD / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    failed = []
    with open(log_dir / f"pipeline__{tag}.log", "a") as log:
        common = ["--model", a.model, "--workers", str(a.workers), "--max-tokens", str(a.max_tokens)]
        for base in a.datasets:
            rc = step(log, f"P2 {base}", ["src.probe_clean", "--dataset", *CONDITIONS[base],
                                          "--spread", "--compare", base, *common])
            if rc:
                failed.append(f"P2 {base}")
        for seed in a.seeds:   # other construction seeds of the built tables (the original has none)
            for base in a.datasets:
                if base in SEEDED:
                    names = [f"{c}_s{seed}" for c in CONDITIONS[base][1:]]
                    if step(log, f"P2 {base} seed {seed}", ["src.probe_clean", "--dataset", *names, "--spread", *common]):
                        failed.append(f"P2 {base} seed {seed}")
        if not a.no_near:
            for ds in NEAR:
                if step(log, f"near-entity {ds}", ["src.near_entities", "run", "--dataset", ds, *common]) or \
                        step(log, f"near-entity screen {ds}", ["src.near_entities", "screen", "--plan-only",
                                                               "--dataset", ds, "--model", a.model]) or \
                        step(log, f"near-entity analyze {ds}", ["src.near_entities", "analyze", "--dataset", ds,
                                                                "--model", a.model]):
                    failed.append(f"near {ds}")
        if a.p1:
            # three settings, as for DeepSeek: no dataset name, with the name, and dirty contexts
            # whose next row has errors (more cells for the leakage test)
            for label, extra in (("P1", []), ("P1 named", ["--named"]), ("P1 error rows", ["--source", "dirty", "--error-rows"])):
                for ds in a.p1_datasets:
                    if step(log, f"{label} {ds}", ["src.probe_rowcont", "--model", a.model, "--dataset", ds, "--n", str(a.p1_n), *extra]):
                        failed.append(f"{label} {ds}")
        log.write(f"\n===== done; failed steps: {failed or 'none'}\n")
    print(json.dumps({"model": a.model, "failed": failed}))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    raise SystemExit("Use tools/core.py for public replay or explicit private validation; no implicit Movies reconstruction")
    main()
