"""E5: traditional (non-LLM) cleaning baselines on the CoRe conditions.

Baran (error correction) and Raha (error detection) from BigDaMa, the authors of the benchmark
datasets. Neither uses outside knowledge here: Baran runs without its pretrained Wikipedia
value models, and Raha without KBVD (its KATARA knowledge-base strategy). If they score alike
on the four conditions while LLM cleaners drop on the surrogates, the drop is the LLM's
knowledge, and the ranking between the two kinds of method can flip.

Modes:
  perfect  Baran told where the errors are (its own benchmark setting): repair only
  raha     Raha detects, Baran repairs: end to end, like the LLM's P2 task
Both use 20 labeled tuples drawn from the clean table (simulated user), several seeds.
Scoring is P2's (case/space-insensitive, identity vs other columns) over the whole table.

Runs in its own venv (raha pins old libraries):
  uv venv .venv-e5 --python 3.11 && uv pip install --python .venv-e5 raha openai python-dotenv
  .venv-e5/bin/python -m src.e5_baselines --dataset hospital hospital_fresh hospital_surrogatewords \
      hospital_surrogate --mode perfect raha --seeds 0 1 2
Results: results/e5/<dataset>__<mode>__seed<k>.json and results/e5/summary.json
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import random
import shutil
import time

import numpy as np

from .data import ARCHIVE, BUILD, RAW, load
from .probe_clean import IDENTITY, base_name, metrics, score_chunk

OUT = Path(os.environ.get("CORE_E5_DIR", ARCHIVE / "e5")).resolve()
WORK = BUILD / "work" / "e5"


class InProcessPool:
    """Stand-in for multiprocessing.Pool: Baran's pool hung with no worker alive on macOS
    (spawn start method), so run its imap in the main process. The initializer sets the
    module globals the workers would have had."""

    def __init__(self, processes=None, initializer=None, initargs=()):
        if initializer:
            initializer(*initargs)

    def imap(self, func, iterable):
        return map(func, iterable)

    def close(self):
        pass


def run_one(dataset: str, mode: str, seed: int) -> dict:
    import raha
    import raha.correction
    raha.correction.Pool = InProcessPool
    work = WORK / f"{dataset}__{mode}__seed{seed}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    # Raha/Baran read the files themselves; our loader aligns dirty headers to the clean ones.
    dirty, clean = load(dataset)
    dirty.to_csv(work / "dirty.csv", index=False)
    clean.to_csv(work / "clean.csv", index=False)
    spec = {"name": dataset, "path": str(work / "dirty.csv"), "clean_path": str(work / "clean.csv")}
    random.seed(seed)
    np.random.seed(seed)
    t0 = time.time()
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet):
        d = raha.dataset.Dataset(spec)
        if mode == "perfect":
            d.detected_cells = dict(d.get_actual_errors_dictionary())
        else:
            det = raha.detection.Detection()
            det.ERROR_DETECTION_ALGORITHMS = ["OD", "PVD", "RVD"]  # no KBVD: it queries a knowledge base
            det.VERBOSE = False
            d.detected_cells = det.run(spec)
            d = raha.dataset.Dataset(spec) if not hasattr(d, "dataframe") else d
            d.detected_cells = dict(d.detected_cells) if isinstance(d.detected_cells, dict) else d.detected_cells
        corr = raha.correction.Correction()
        corr.PRETRAINED_VALUE_BASED_MODELS_PATH = ""  # no Wikipedia value models
        corr.VERBOSE = False
        corr.SAVE_RESULTS = False
        corr.NUM_WORKERS = 1
        fixes = corr.run(d)
    seconds = time.time() - t0
    cols = list(clean.columns)
    preds = [{"row": i + 1, "column": cols[j], "value": v} for (i, j), v in fixes.items()]
    counts = score_chunk(dirty, clean, preds, IDENTITY.get(base_name(dataset), []))
    res = {"dataset": dataset, "mode": mode, "seed": seed, "seconds": round(seconds),
           "detected": len(d.detected_cells), "corrections": len(fixes), "counts": counts,
           "fixes": [[int(i), cols[int(j)], v] for (i, j), v in fixes.items()],  # for re-scoring
           **{g: metrics(counts[g]) for g in ("all", "identity", "other")}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{dataset}__{mode}__seed{seed}.json").write_text(json.dumps(res, indent=1))
    shutil.rmtree(work, ignore_errors=True)
    return res


def summarize() -> dict:
    rows = [json.loads(p.read_text()) for p in sorted(OUT.glob("*__seed*.json"))]
    groups = {}
    for r in rows:
        groups.setdefault((r["dataset"], r["mode"]), []).append(r)
    summary = {}
    for (ds, mode), rs in sorted(groups.items()):
        f1 = {g: [r[g]["repair_f1"] for r in rs] for g in ("all", "identity", "other")}
        summary[f"{ds}|{mode}"] = {"seeds": len(rs),
                                   **{f"{g}_repair_f1": round(float(np.mean(v)), 3) for g, v in f1.items()},
                                   **{f"{g}_sd": round(float(np.std(v)), 3) for g, v in f1.items()},
                                   "minutes": round(np.mean([r["seconds"] for r in rs]) / 60, 1)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", nargs="+", required=True)
    ap.add_argument("--mode", nargs="+", default=["perfect"], choices=["perfect", "raha"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    a = ap.parse_args()
    for mode in a.mode:
        for ds in a.dataset:
            for s in a.seeds:
                if (OUT / f"{ds}__{mode}__seed{s}.json").exists():
                    continue  # resume
                r = run_one(ds, mode, s)
                print(json.dumps({k: r[k] for k in ("dataset", "mode", "seed", "seconds", "detected", "corrections")}
                                 | {g: round(r[g]["repair_f1"], 3) for g in ("all", "identity", "other")}), flush=True)
    print(json.dumps(summarize(), indent=1))


if __name__ == "__main__":
    main()
