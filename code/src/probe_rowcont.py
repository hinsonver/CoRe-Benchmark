"""Probe P1: row continuation (verbatim memorization of a cleaning benchmark).

Given k consecutive CSV rows (from the clean or the dirty version), ask the model for the
next row and compare it cell by cell with the true next row.

Cells whose correct value already appears in the same column of the context are
"inferable" (the model can copy them). Row-counter columns (value = previous + 1, e.g.
flights' tuple_id) are excluded from cell scoring altogether, since counting is not memory.
Memorization evidence comes only from **non-inferable** cells, and within those from
**hard** cells that two structural guessers (column mode, previous->next transition) also
miss: `acc_hard` should be ~0 for a model that never saw the table. `per_column` shows
where hits come from (e.g. hospital MeasureCode follows a fixed order: not memory).

With a dirty context we also measure **ground-truth leakage**: for next-row cells that are
erroneous in the dirty table, how often does the model emit the *clean* value (which the
context does not contain)?

Usage:
  .venv/bin/python -m src.probe_rowcont --model mock:echo --dataset flights --n 5
  .venv/bin/python -m src.probe_rowcont --model deepseek:deepseek-chat --dataset all --n 50
"""
import argparse
import collections
import csv
import io
import json
import os
import random
import sys
from pathlib import Path

from .clients import complete
from .data import DATASETS, ROOT, counter_columns, load, to_csv_block

SYSTEM = "You are a CSV completion engine. Output exactly one CSV line and nothing else."
PROMPT = (
    "{hint}The following are consecutive rows of a CSV file, including its header.\n"
    "Write the next row of the file exactly as it appears in the file.\n\n{block}\n"
)
HINT = "These rows come from the '{name}' dataset used in data cleaning research.\n"


def parse_row(text: str, ncols: int) -> list[str] | None:
    line = next((l for l in text.strip().strip("`").splitlines() if l.strip()), "")
    try:
        row = next(csv.reader(io.StringIO(line)))
    except StopIteration:
        return None
    return row if len(row) == ncols else None


def structural_baselines(df):
    """Counts behind the non-memorizing guessers, fit on the table itself:
    - freq:  how often each value occurs in a column (guess: the column mode, e.g. "100%");
    - trans: which value follows which in consecutive rows (fixed orderings such as hospital
             measure codes pn-4 -> pn-5c);
    - fds:   functional dependencies d -> c (hospital Condition fixed by MeasureCode).
    Guesses are made leave-one-out (see `_top`): the cell being scored never counts as its own
    evidence, otherwise a unique value's own successor would "predict" it and the baseline
    would itself be memorizing the table."""
    freq = {c: collections.Counter(df[c]) for c in df.columns}
    trans = {}
    for c in df.columns:
        nxt = collections.defaultdict(collections.Counter)
        for a, b in zip(df[c].iloc[:-1], df[c].iloc[1:]):
            nxt[a][b] += 1
        trans[c] = nxt
    fds = collections.defaultdict(list)
    for d in df.columns:
        if df[d].nunique() > 0.5 * len(df):
            continue  # near-key columns trivially determine everything
        for c in df.columns:
            if c == d:
                continue
            pairs = collections.defaultdict(collections.Counter)
            for a, b in zip(df[d], df[c]):
                pairs[a][b] += 1
            if sum(max(v.values()) for v in pairs.values()) >= 0.99 * len(df):
                fds[c].append((d, pairs))
    return freq, trans, fds


def _top(counter, exclude=None):
    """Most common key after removing one occurrence of `exclude` (leave-one-out)."""
    best, n = None, 0
    for key, v in counter.items():
        v -= key == exclude
        if v > n:
            best, n = key, v
    return best


def structural_guesses(col, prev_row, row, base):
    """Values the structural guessers propose for `row[col]` given the previous row."""
    freq, trans, fds = base
    guesses = {_top(freq[col], row[col]), _top(trans[col].get(prev_row[col], {}), row[col])}
    for d, pairs in fds.get(col, []):
        d_guess = _top(trans[d].get(prev_row[d], {}), row[d])
        if d_guess is not None:
            guesses.add(_top(pairs.get(d_guess, {}), row[col] if d_guess == row[d] else None))
    # Arithmetic step: previous numeric value +/- 1 (ids that count up or down).
    try:
        p = float(prev_row[col])
        for v in (p + 1, p - 1):
            guesses.add(str(int(v)) if v.is_integer() else str(v))
    except ValueError:
        pass
    guesses.discard(None)
    return guesses


def run(model: str, name: str, source: str, n: int, k: int, named: bool, seed: int,
        error_rows: bool = False) -> dict:
    dirty, clean = load(name, max_rows=5000 if name == "tax" else None)
    ctx_df = dirty if source == "dirty" else clean
    skip = set(counter_columns(clean))
    base = structural_baselines(ctx_df)
    cbase = structural_baselines(clean)
    freq, trans, _ = base
    per_col = collections.defaultdict(lambda: collections.Counter())
    rng = random.Random(seed)
    pool = range(k, len(clean))
    if error_rows:  # only target rows that contain at least one dirty cell (more leak cells)
        has_err = dirty.ne(clean).any(axis=1)
        pool = [i for i in pool if has_err[i]]
    # Draw 100 (or n, if larger) and keep the first n: smaller runs are then a prefix of the
    # n=100 run, so they reuse its cached answers and results stay comparable across n.
    starts = rng.sample(list(pool), min(max(n, 100), len(pool)))[:n]
    trials, agg = [], {"inf": [0, 0], "noninf": [0, 0], "hard": [0, 0], "leak": [0, 0],
                       "leak_hard": [0, 0], "exact": 0, "parsed": 0, "failed": 0}
    streak = 0  # consecutive failed calls

    for i in starts:
        ctx = ctx_df.iloc[i - k : i]
        prompt = PROMPT.format(hint=HINT.format(name=name) if named else "", block=to_csv_block(ctx))
        try:
            # Local models are slow and keep writing rows; P1 reads only the first line.
            out = complete(model, prompt, system=SYSTEM, max_tokens=512,
                           stop=["\n"] if model.startswith("local:") else None)
        except Exception as e:  # a hung/crashed server must not kill the whole run
            print(f"call failed ({name} row {i}): {type(e).__name__}: {e}", file=sys.stderr)
            agg["failed"] += 1
            trials.append({"row": i, "output": "", "parsed": False, "error": type(e).__name__})
            streak += 1
            if streak >= 3:  # the server is gone (e.g. Metal OOM): stop so the caller can restart it
                sys.exit(f"aborting {name}: {streak} consecutive failed calls")
            continue
        streak = 0
        pred = parse_row(out, clean.shape[1])
        truth, dtruth = clean.iloc[i].tolist(), dirty.iloc[i].tolist()
        rec = {"row": i, "output": out, "parsed": pred is not None}
        if pred is not None:
            agg["parsed"] += 1
            agg["exact"] += pred == (dtruth if source == "dirty" else truth)
            for j, col in enumerate(clean.columns):
                if col in skip:
                    continue
                seen = set(ctx[col])
                target = dtruth[j] if source == "dirty" else truth[j]
                bucket = "inf" if target in seen else "noninf"
                agg[bucket][0] += pred[j] == target
                agg[bucket][1] += 1
                if bucket == "noninf":
                    f_ok = _top(freq[col], target) == target
                    t_ok = _top(trans[col].get(ctx[col].iloc[-1], {}), target) == target
                    s_ok = target in structural_guesses(col, ctx.iloc[-1], ctx_df.iloc[i], base)
                    pc = per_col[col]
                    pc["n"] += 1; pc["model"] += pred[j] == target; pc["freq"] += f_ok; pc["trans"] += t_ok
                    pc["structural"] += s_ok
                    # "Hard" cells: no structural guesser gets them -> real memory evidence.
                    if not s_ok:
                        agg["hard"][0] += pred[j] == target
                        agg["hard"][1] += 1
                # Leakage: dirty cell is wrong and the clean value is not in the context.
                if source == "dirty" and dtruth[j] != truth[j] and truth[j] not in seen:
                    agg["leak"][0] += pred[j] == truth[j]
                    agg["leak"][1] += 1
                    if truth[j] not in structural_guesses(col, clean.iloc[i - 1], clean.iloc[i], cbase):
                        agg["leak_hard"][0] += pred[j] == truth[j]
                        agg["leak_hard"][1] += 1
        trials.append(rec)

    rate = lambda a: round(a[0] / a[1], 4) if a[1] else None
    summary = {
        "model": model, "dataset": name, "source": source, "named": named, "n": n, "k": k,
        "seed": seed, "error_rows": error_rows, "skipped_counter_cols": sorted(skip), "parse_rate": round(agg["parsed"] / len(starts), 4),
        "exact_row_match": round(agg["exact"] / len(starts), 4), "failed_calls": agg["failed"],
        "acc_inferable": rate(agg["inf"]), "acc_noninferable": rate(agg["noninf"]),
        "noninferable_cells": agg["noninf"][1],
        "acc_hard": rate(agg["hard"]), "hard_cells": agg["hard"][1],
        "leak_rate": rate(agg["leak"]), "leak_cells": agg["leak"][1],
        "leak_hard_rate": rate(agg["leak_hard"]), "leak_hard_cells": agg["leak_hard"][1],
    }
    # Per-column breakdown on non-inferable cells: model vs. the two structural guessers.
    summary["per_column"] = {
        c: {"n": v["n"], "model": round(v["model"] / v["n"], 3),
            "freq": round(v["freq"] / v["n"], 3), "trans": round(v["trans"] / v["n"], 3),
            "structural": round(v["structural"] / v["n"], 3)}
        for c, v in per_col.items() if v["n"]
    }
    return {"summary": summary, "trials": trials}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dataset", default="all")
    ap.add_argument("--source", choices=["clean", "dirty", "both"], default="both")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--named", action="store_true", help="tell the model the dataset name")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--error-rows", action="store_true", help="sample only rows containing errors")
    args = ap.parse_args()

    names = DATASETS if args.dataset == "all" else [args.dataset]
    sources = ["clean", "dirty"] if args.source == "both" else [args.source]
    out_dir = Path(os.environ.get("CORE_P1_DIR", ROOT / "artifacts" / "raw_outputs" / "p1")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        for source in sources:
            res = run(args.model, name, source, args.n, args.k, args.named, args.seed, args.error_rows)
            tag = f"{args.model.replace(':', '_').replace('/', '_')}__{name}__{source}__{'named' if args.named else 'anon'}{'__err' if args.error_rows else ''}"
            (out_dir / f"{tag}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
            brief = {k: v for k, v in res["summary"].items() if k != "per_column"}
            print(json.dumps(brief, ensure_ascii=False))


if __name__ == "__main__":
    main()
