"""E4: a published LLM cleaning method (TabClean) on the four CoRe conditions.

TabClean (third_party/TabClean, run by scripts/run_tabclean.py with DeepSeek-V4-Pro through the
relay) profiles the table, draws a development sample of rows whose ground truth it uses,
writes cleaning code with several agents, and applies the best code to the whole table. It is
run unchanged on each condition; we score its output with the P2 rules.

Rows of TabClean's development sample are left out of scoring: the method sees their ground
truth (as Baran's labeled tuples are left out in the aligned comparison). The sample is
reproduced from TabClean's own draw (DataFrame.sample(n, random_state=42) on the dirty table,
n = the rows of its dev_dirty.csv).

Steps:
  .venv/bin/python -m src.e4 prepare                 # aligned dirty/clean CSVs per condition
  .venv-tabclean/bin/python scripts/run_tabclean.py --csv results/e4/inputs/<cond>/dirty.csv \\
      --gt results/e4/inputs/<cond>/clean.csv --tag <cond>
  .venv/bin/python -m src.e4 score                   # results/e4/summary.json
"""
import argparse
import json
import os
from pathlib import Path

import pandas as pd

from .data import ARCHIVE, load
from .probe_clean import IDENTITY, base_name, metrics, norm

E4 = Path(os.environ.get("CORE_E4_DIR", ARCHIVE / "e4")).resolve()
CONDITIONS = {"hospital": ["hospital", "hospital_fresh", "hospital_surrogatewords", "hospital_surrogate"],
              "movies": ["movies", "movies_fresh", "movies_surrogatewords", "movies_surrogate"],
              "beers": ["beers_orig", "beers_fresh", "beers_surrogatewords", "beers_surrogate"]}


def prepare() -> None:
    """TabClean reads the files itself: write each condition with the clean table's headers."""
    for conds in CONDITIONS.values():
        for c in conds:
            d, cl = load(c)
            out = E4 / "inputs" / c
            out.mkdir(parents=True, exist_ok=True)
            d.to_csv(out / "dirty.csv", index=False)
            cl.to_csv(out / "clean.csv", index=False)
            print(c, d.shape, int((d.values != cl.values).sum()), "error cells")


def dev_rows(cond: str, n_rows: int) -> set[int]:
    work = E4 / "tabclean" / cond
    n_dev = len(pd.read_csv(work / "dev_dirty.csv", dtype=str, keep_default_na=False))
    return set(pd.RangeIndex(n_rows).to_series().sample(n=n_dev, random_state=42).index)


def score(cond: str) -> dict:
    if cond == "rayyan":
        from .rayyan_replay import replay
        return replay(E4.parents[2])["tabclean"]
    dirty, clean = load(cond)
    out = pd.read_csv(E4 / "tabclean" / cond / "final_cleaned.csv", dtype=str, keep_default_na=False)
    if out.shape != clean.shape:
        raise ValueError(f"{cond}: output shape {out.shape} != {clean.shape}")
    out.columns = clean.columns
    skip = dev_rows(cond, len(clean))
    ident = set(IDENTITY[base_name(cond)])
    counts = {g: {"errors": 0, "predicted": 0, "repaired": 0, "detected": 0} for g in ("all", "identity", "other")}
    for i in range(len(clean)):
        if i in skip:
            continue
        for c in clean.columns:
            d, g, v = dirty.at[i, c], clean.at[i, c], out.at[i, c]
            err, changed = d != g, norm(v) != norm(d)
            for grp in ("all", "identity" if c in ident else "other"):
                counts[grp]["errors"] += err
                counts[grp]["predicted"] += changed
                counts[grp]["detected"] += changed and err
                counts[grp]["repaired"] += changed and err and norm(v) == norm(g)
    return {"scored_rows": len(clean) - len(skip), "dev_rows": len(skip),
            **{g: metrics(counts[g]) for g in counts}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["prepare", "score"])
    a = ap.parse_args()
    if a.step == "prepare":
        prepare()
        return
    summary = {}
    for conds in CONDITIONS.values():
        for c in conds:
            if (E4 / "tabclean" / c / "final_cleaned.csv").exists():
                s = score(c)
                summary[c] = s
                print(f"{c:24s} rows {s['scored_rows']} (dev {s['dev_rows']}) | repair F1 all {s['all']['repair_f1']:.3f}"
                      f" identity {s['identity']['repair_f1']:.3f} other {s['other']['repair_f1']:.3f}"
                      f" | predicted {s['all']['predicted']} repaired {s['all']['repaired']} of {s['all']['errors']}")
    (E4 / "summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
