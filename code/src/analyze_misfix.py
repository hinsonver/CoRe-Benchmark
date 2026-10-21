"""Classify the model's wrong edits on identity cells in the P2 runs: which are knowledge at work?

A wrong edit is a predicted value for an identity cell that is neither a no-op nor the correct
repair. Each one gets the first matching label:
  format    only whitespace/punctuation differs from the dirty value ("A,B" -> "A, B")
  restore   (surrogates) the prediction is the real value the surrogate replaced
  real      the prediction (or, for people lists, a newly added person) is a real entity of that
            kind: US hospital/city/county names (CMS), IMDb people, beers/breweries/US cities
  misrepair the cell was an error and the guess is wrong, with no real entity involved
  tweak     a correct cell changed by a small edit (edit ratio >= 0.8), e.g. "Oskgargar" -> "Oskgar"
  other
"restore" + "real" are knowledge-induced wrong edits: the model writes what it knows over what
the table says.

Usage: .venv/bin/python -m src.analyze_misfix  (writes results/p2_clean/misfix_summary.json)
"""
import collections
import difflib
import gzip
import json
import re

import pandas as pd

from .data import RAW, ROOT, load
from .probe_clean import IDENTITY, OUT, base_name, norm, parse

MODEL = "custom_deepseek_deepseek-v4-pro"
PEOPLE = {"Director", "Creator", "Actors"}
# condition -> (result file, table name for load(), original table whose values surrogates replaced)
RUNS = {}
for base, orig in (("hospital", "hospital"), ("movies", "movies"), ("beers", "beers_orig")):
    for cond in (orig, f"{base}_fresh", f"{base}_surrogatewords", f"{base}_surrogate"):
        RUNS[cond] = (OUT / f"{MODEL}__{cond}__k20__spread.json", cond, orig)
for cond in ("beers_fresh", "beers_surrogatewords", "beers_surrogate"):  # first Beers build, 09-29
    RUNS[f"{cond}@v1"] = (OUT / "_beers_v1" / f"{MODEL}__{cond}__k20__spread.json", f"_beers_v1/{cond}", "beers_orig")
# second build: words-surrogate cities were plain common words ("Maternal"), replaced 09-29
RUNS["beers_surrogatewords@v2"] = (OUT / "_beers_v2" / f"{MODEL}__beers_surrogatewords__k20__spread.json",
                                   "_beers_v2/beers_surrogatewords", "beers_orig")
# third build: multi-word cities became two compounds ("Creekgrace Quietshadow"), replaced 09-29
RUNS["beers_surrogatewords@v3"] = (OUT / "_beers_v3" / f"{MODEL}__beers_surrogatewords__k20__spread.json",
                                   "_beers_v3/beers_surrogatewords", "beers_orig")


def squash(v: str) -> str:
    return re.sub(r"[\W_]+", "", norm(v))


def people(v: str) -> list[str]:
    return [norm(p) for p in re.split(r",", v) if p.strip()]


def wrong_edits(cond: str):
    path, table, orig = RUNS[cond]
    dirty, clean = load(table)
    _, oclean = load(orig)
    ident = IDENTITY[base_name(table.split("/")[-1])]
    for c in json.loads(path.read_text())["chunks"]:
        rows = c["rows"]
        for p in parse(c["output"]):
            try:
                r = int(p["row"]) - 1
            except (TypeError, ValueError):
                continue
            col, v = str(p["column"]), str(p["value"]).strip()
            if not 0 <= r < len(rows) or col not in ident:
                continue
            i = rows[r]
            dv, cv = dirty.at[i, col], clean.at[i, col]
            if norm(v) in (norm(dv), norm(cv)):
                continue
            yield {"cond": cond, "col": col, "dirty": dv, "pred": v, "clean": cv,
                   "real_orig": oclean.at[i, col], "error_cell": dv != cv}


# --------------------------------------------------------------------------- vocabularies
def cms_vocab() -> dict[str, set[str]]:
    g = pd.read_csv(RAW / "_cms" / "xubh-q36u.csv", dtype=str, keep_default_na=False)
    return {"HospitalName": set(g["Facility Name"].map(norm)), "Address1": set(g["Address"].map(norm)),
            "City": set(g["City/Town"].map(norm)), "CountyName": set(g["County/Parish"].map(norm))}


def beers_vocab(cities: set[str]) -> dict[str, set[str]]:
    _, full = load("beers")
    w = pd.read_csv(RAW / "_wikidata" / "beers_raw.csv", dtype=str, keep_default_na=False)
    b = pd.read_csv(RAW / "_wikidata" / "breweries.csv", dtype=str, keep_default_na=False)
    return {"beer-name": set(full["beer-name"].map(norm)) | set(w["bLabel"].map(norm)),
            "brewery-name": set(full["brewery-name"].map(norm)) | set(w["mLabel"].map(norm)),
            "city": cities | set(full["city"].map(norm)) | set(b["cityLabel"].map(norm))}


def imdb_people(candidates: set[str]) -> set[str]:
    """The candidates that are the name of some person on IMDb (one pass over name.basics)."""
    found = set()
    with gzip.open(RAW / "_imdb" / "name.basics.tsv.gz", "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            n = norm(line.split("\t", 2)[1])
            if n in candidates:
                found.add(n)
    return found


# --------------------------------------------------------------------------- classification
def classify(e: dict, vocab: dict[str, set[str]], imdb: set[str]) -> str:
    dv, pv = e["dirty"], e["pred"]
    if squash(pv) == squash(dv):
        return "format"
    surrogate = "surrogate" in e["cond"]
    if e["col"] in PEOPLE:
        new = [p for p in people(pv) if p not in people(dv)]
        if surrogate and any(p in people(e["real_orig"]) for p in new):
            return "restore"
        if any(p in imdb for p in new):
            return "real"
    else:
        if surrogate and norm(pv) == norm(e["real_orig"]):
            return "restore"
        if norm(pv) in vocab.get(e["col"], set()):
            return "real"
    if e["error_cell"]:
        return "misrepair"
    if difflib.SequenceMatcher(None, norm(dv), norm(pv)).ratio() >= 0.8:
        return "tweak"
    return "other"


def main() -> None:
    edits = {cond: list(wrong_edits(cond)) for cond in RUNS if RUNS[cond][0].exists()}
    cms = cms_vocab()
    vocab = {**cms, **beers_vocab(cms["City"])}
    cand = {p for es in edits.values() for e in es if e["col"] in PEOPLE for p in people(e["pred"])}
    imdb = imdb_people(cand)
    summary = {}
    for cond, es in edits.items():
        _, table, _ = RUNS[cond]
        dirty, clean = load(table)
        ident = IDENTITY[base_name(table.split("/")[-1])]
        cells = len(clean) * len(ident)
        labels = collections.Counter()
        examples = collections.defaultdict(list)
        for e in es:
            lab = classify(e, vocab, imdb)
            labels[lab] += 1
            if len(examples[lab]) < 6:
                examples[lab].append({k: e[k] for k in ("col", "dirty", "pred", "real_orig")})
        summary[cond] = {"identity_cells": cells, "wrong_edits": len(es), "labels": dict(labels),
                         "knowledge_induced": labels["restore"] + labels["real"],
                         "knowledge_induced_on_correct_cells": sum(
                             1 for e in es if not e["error_cell"] and classify(e, vocab, imdb) in ("restore", "real")),
                         "examples": examples}
    (OUT / "misfix_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"{'condition':30s} {'wrong':>5s} {'format':>6s} {'restore':>7s} {'real':>5s} {'misrep':>6s} {'tweak':>5s} {'other':>5s} {'knowl.':>6s}")
    for cond, s in summary.items():
        L = s["labels"]
        print(f"{cond:30s} {s['wrong_edits']:5d} {L.get('format', 0):6d} {L.get('restore', 0):7d} {L.get('real', 0):5d} "
              f"{L.get('misrepair', 0):6d} {L.get('tweak', 0):5d} {L.get('other', 0):5d} {s['knowledge_induced']:6d}")


if __name__ == "__main__":
    main()
