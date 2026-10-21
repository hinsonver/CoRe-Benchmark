"""Probe P2: the cleaning task itself, run on original / fresh / surrogate versions of a table.

The table is cut into consecutive chunks of `k` rows. For each chunk the model sees the
dirty rows and returns the cells it believes are wrong with their corrected values (JSON).
Scores are the usual cleaning metrics (repair precision / recall / F1, detection F1),
reported for all columns and separately for identity columns (names, addresses...), where
memorization or world knowledge would help.

Reading the three conditions:
  original - fresh      -> memory of this particular table
  fresh    - surrogate  -> world knowledge about the entities
The surrogate keeps the original's error cells exactly, so original vs surrogate is paired
chunk by chunk.

Usage:
  .venv/bin/python -m src.probe_clean --model custom:deepseek/deepseek-v4-pro --dataset hospital
  .venv/bin/python -m src.probe_clean --model custom:deepseek/deepseek-v4-pro --compare hospital
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import random
import re
from pathlib import Path

from .clients import complete_json
from .data import ARCHIVE, load, to_csv_block

OUT = Path(os.environ.get("CORE_P2_DIR", ARCHIVE / "p2")).resolve()
IDENTITY = {"hospital": ["ProviderNumber", "HospitalName", "Address1", "City", "ZipCode",
                         "CountyName", "PhoneNumber"],
            "movies": ["Id", "Name", "Director", "Creator", "Actors"],
            "beers": ["beer-name", "brewery-name", "city"],
            "rayyan": ["article_title", "journal_title", "author_list"]}
# Entity key per dataset, for --spread chunks (one row per entity per chunk).
ENTITY = {"hospital": "ProviderNumber", "movies": "Id", "beers": "brewery_id", "rayyan": "id"}
# Original-condition table when the base name is taken by the full benchmark ("beers" is the
# full Raha table that P1 uses; its 1000-row CoRe subset is "beers_orig").
ORIGINAL = {"beers": "beers_orig"}
SYSTEM = "You are a meticulous data cleaning assistant. Reply with JSON only."
PROMPT = (
    "The CSV table below contains some erroneous cells (for example typos or corrupted "
    "values). The first column `_row` numbers the rows.\n"
    "Find the erroneous cells and give their correct values. Only list cells you believe "
    "are wrong; do not rewrite correct cells.\n"
    'Reply with JSON: {{"corrections": [{{"row": <_row>, "column": "<column name>", '
    '"value": "<corrected value>"}}]}}\n\n{block}\n'
)


def base_name(dataset: str) -> str:
    return dataset.split("_")[0]


def parse(text: str) -> list[dict]:
    """Corrections from a model reply; tolerant of code fences and stray prose."""
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e <= s:
        return []
    try:
        obj = json.loads(text[s : e + 1])
    except json.JSONDecodeError:
        obj = {"corrections": []}
        for item in re.findall(r"\{[^{}]*\}", text[s : e + 1]):
            try:
                obj["corrections"].append(json.loads(item))
            except json.JSONDecodeError:
                pass
    out = obj.get("corrections", []) if isinstance(obj, dict) else []
    return [c for c in out if isinstance(c, dict) and {"row", "column", "value"} <= set(c)]


def norm(v) -> str:
    """Values are compared ignoring case and spacing, including spaces around commas.
    - Case: on the surrogate table DeepSeek wrote fixes in Title Case ("Morcalzar" for
      "morcalzar") and re-cased correct cells ("al" -> "AL"), which strict matching counted as
      failed repairs and false corrections.
    - Commas (unified rule since 09-29): on fictitious people lists DeepSeek rewrote "A,B" as
      "A, B" (160 cells on the Movies pseudo surrogate, 2 on the original), a format-only change."""
    return re.sub(r"\s*,\s*", ",", " ".join(str(v).lower().split()))


def score_chunk(dirty, clean, preds, identity) -> dict:
    """Cell-level counts for one chunk. A prediction equal to the dirty value is a no-op."""
    cols = list(clean.columns)
    errors = {(r, c) for r in range(len(clean)) for j, c in enumerate(cols)
              if dirty.iat[r, j] != clean.iat[r, j]}
    pred = {}
    for p in preds:
        try:
            r = int(p["row"]) - 1
        except (TypeError, ValueError):
            continue
        c, v = str(p["column"]), str(p["value"]).strip()
        if 0 <= r < len(clean) and c in cols and norm(v) != norm(dirty.iat[r, cols.index(c)]):
            pred[(r, c)] = v
    counts = {}
    for group, keep in (("all", lambda c: True), ("identity", lambda c: c in identity),
                        ("other", lambda c: c not in identity)):
        E = {x for x in errors if keep(x[1])}
        P = {x: v for x, v in pred.items() if keep(x[1])}
        repaired = sum(1 for x, v in P.items()
                       if x in E and norm(v) == norm(clean.iat[x[0], cols.index(x[1])]))
        detected = sum(1 for x in P if x in E)
        counts[group] = {"errors": len(E), "predicted": len(P), "repaired": repaired, "detected": detected}
    return counts


def metrics(c: dict) -> dict:
    f = lambda a, b: 2 * a * b / (a + b) if a + b else 0.0
    p = c["repaired"] / c["predicted"] if c["predicted"] else 0.0
    r = c["repaired"] / c["errors"] if c["errors"] else 0.0
    dp = c["detected"] / c["predicted"] if c["predicted"] else 0.0
    dr = c["detected"] / c["errors"] if c["errors"] else 0.0
    return {"repair_p": round(p, 4), "repair_r": round(r, 4), "repair_f1": round(f(p, r), 4),
            "detect_f1": round(f(dp, dr), 4), **c}


def total(chunks: list[dict], group: str) -> dict:
    return {k: sum(ch["counts"][group][k] for ch in chunks)
            for k in ("errors", "predicted", "repaired", "detected")}


def spread_chunks(clean, key: str, k: int) -> list[list[int]]:
    """Chunks of k rows from k *different* entities, so a corrupted name or address cannot be
    copied from a sibling row of the same entity: fixing it then needs knowledge or memory.
    Each chunk takes one row from each of the k entities with the most rows left (ties by
    first row), so tables with the same entity grouping (original, surrogate) get identical
    chunks and stay paired."""
    left = {}
    for i, e in enumerate(clean[key]):
        left.setdefault(e, []).append(i)
    chunks = []
    while True:
        live = sorted((e for e in left if left[e]), key=lambda e: (-len(left[e]), left[e][0]))
        if len(live) < k:
            return chunks
        chunks.append(sorted(left[e].pop(0) for e in live[:k]))


def run(model: str, dataset: str, k: int, max_chunks: int | None, seed: int,
        spread: bool = False, workers: int = 1, max_tokens: int = 4096) -> dict:
    """workers > 1 sends chunks concurrently (a vLLM server batches them); max_tokens caps the
    reply (4096 by default, which the cached API runs used; OLMo-2's 4k context needs less)."""
    dirty, clean = load(dataset)
    base = base_name(dataset)
    identity = IDENTITY.get(base, [])
    if spread:
        row_sets = spread_chunks(clean, ENTITY[base], k)
    else:
        row_sets = [list(range(s, s + k)) for s in range(0, len(clean) - k + 1, k)]
    if max_chunks and max_chunks < len(row_sets):
        keep = sorted(random.Random(seed).sample(range(len(row_sets)), max_chunks))
        row_sets = [row_sets[i] for i in keep]
    def ask(rows):
        shown = dirty.iloc[rows].reset_index(drop=True)
        shown.insert(0, "_row", range(1, len(rows) + 1))
        return complete_json(model, PROMPT.format(block=to_csv_block(shown)), system=SYSTEM, max_tokens=max_tokens)

    with ThreadPoolExecutor(workers) as ex:
        outputs = list(ex.map(ask, row_sets))
    chunks = []
    for rows, out in zip(row_sets, outputs):
        d = dirty.iloc[rows].reset_index(drop=True)
        c = clean.iloc[rows].reset_index(drop=True)
        preds = parse(out)
        chunks.append({"start": rows[0], "rows": rows, "n_pred": len(preds),
                       "counts": score_chunk(d, c, preds, identity), "output": out})
    summary = {"model": model, "dataset": dataset, "k": k, "spread": spread, "chunks": len(chunks),
               **{g: metrics(total(chunks, g)) for g in ("all", "identity", "other")}}
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{model.replace(':', '_').replace('/', '_')}__{dataset}__k{k}{'__spread' if spread else ''}"
    (OUT / f"{tag}.json").write_text(json.dumps({"summary": summary, "chunks": chunks},
                                                ensure_ascii=False, indent=1))
    return summary


def f1_of(chunks, group):
    return metrics(total(chunks, group))["repair_f1"]


def bootstrap_diff(a, b, group, paired, n=2000, seed=0):
    """repair-F1(a) - repair-F1(b) with a 95% CI from resampling chunks."""
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        if paired:
            idx = [rng.randrange(len(a)) for _ in a]
            sa, sb = [a[i] for i in idx], [b[i] for i in idx]
        else:
            sa = [a[rng.randrange(len(a))] for _ in a]
            sb = [b[rng.randrange(len(b))] for _ in b]
        diffs.append(f1_of(sa, group) - f1_of(sb, group))
    diffs.sort()
    return f1_of(a, group) - f1_of(b, group), diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def compare(model: str, base: str, k: int, spread: bool = False) -> None:
    tag = model.replace(":", "_").replace("/", "_")
    sfx = "__spread" if spread else ""
    orig = ORIGINAL.get(base, base)
    conds = [orig, f"{base}_fresh", f"{base}_surrogatewords", f"{base}_surrogate"]
    res = {d: json.loads((OUT / f"{tag}__{d}__k{k}{sfx}.json").read_text())
           for d in conds if (OUT / f"{tag}__{d}__k{k}{sfx}.json").exists()}
    print(f"{'condition':20s} {'group':9s} {'errors':>6s} {'pred':>5s} {'rep_P':>6s} {'rep_R':>6s} {'rep_F1':>6s} {'det_F1':>6s}")
    for d, r in res.items():
        for g in ("all", "identity", "other"):
            m = r["summary"][g]
            print(f"{d:20s} {g:9s} {m['errors']:6d} {m['predicted']:5d} {m['repair_p']:6.3f} "
                  f"{m['repair_r']:6.3f} {m['repair_f1']:6.3f} {m['detect_f1']:6.3f}")
    o, f, s = (res[d]["chunks"] for d in (orig, f"{base}_fresh", f"{base}_surrogate"))
    w = res.get(f"{base}_surrogatewords", {}).get("chunks")
    pairs = [("original - fresh          (memory)", o, f, False),
             ("fresh - surrogate         (all knowledge)", f, s, False),
             ("original - surrogate      (paired)", o, s, True)]
    if w:  # words surrogate splits knowledge into entity vs spelling knowledge
        pairs += [("fresh - words-surrogate   (entity knowledge)", f, w, False),
                  ("words - pseudo surrogate  (spelling knowledge)", w, s, True)]
    print("\nrepair-F1 differences, 95% bootstrap CI over chunks (* = CI excludes 0):")
    for g in ("all", "identity", "other"):
        for name, a, b, paired in pairs:
            d, lo, hi = bootstrap_diff(a, b, g, paired)
            flag = "*" if lo > 0 or hi < 0 else " "
            print(f"  {g:9s} {name:46s} {d:+.3f}  [{lo:+.3f}, {hi:+.3f}] {flag}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dataset", nargs="*", default=[])
    ap.add_argument("--compare", help="base dataset name: compare its three conditions")
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--max-chunks", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1, help="concurrent requests (vLLM batches them)")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--spread", action="store_true",
                    help="each chunk holds rows of k different entities (see spread_chunks)")
    args = ap.parse_args()
    for d in args.dataset:
        s = run(args.model, d, args.k, args.max_chunks, args.seed, args.spread, args.workers, args.max_tokens)
        brief = {g: {x: s[g][x] for x in ("repair_p", "repair_r", "repair_f1", "detect_f1", "errors")}
                 for g in ("all", "identity", "other")}
        print(json.dumps({"dataset": d, **brief}, ensure_ascii=False))
    if args.compare:
        compare(args.model, args.compare, args.k, args.spread)


if __name__ == "__main__":
    main()
