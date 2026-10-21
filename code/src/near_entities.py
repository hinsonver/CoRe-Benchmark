"""Near-entity condition: does the model overwrite correct table values with what it knows?

On the pseudo-syllable surrogate tables (the model knows none of their entities) some entities
are replaced by entities the model does know, with facts that contradict its knowledge but are
consistent within the table:

  type A "real name, other facts": a famous hospital / brewery / film under its real name, with
          another real location (or, for films, another real director)
          e.g. Anchor Brewing Company, Sacramento CA
  type B "near name": the famous name one vowel off, same other facts
          e.g. Anchir Brewing Company, Sacramento CA
  control the entity keeps its surrogate name, same other facts
Versions differ only in the name cell, so edits beyond the control's are knowledge at work.

Two factors: support (the entity has 1 or 3 identical rows in a chunk; hospital and beers
only, a film is one row) and prompt (the standard P2 prompt, or one that tells the model to
rely on evidence in the table). Chunks are 20 rows: 3 target entities plus filler rows from
distinct other entities, identical across types, versions and prompts.

Only entities the model knows are used: `screen` asks the model where each candidate is
located (who directed each film) and keeps the ones it gets right.

Usage: .venv/bin/python -m src.near_entities {candidates,screen,build,run,analyze} [--model M]
"""
import argparse
import collections
import concurrent.futures as cf
import gzip
import json
import os
from pathlib import Path
import random
import re
import sys
import unicodedata

import pandas as pd

from .clients import complete, complete_json
from .data import ARCHIVE, RAW, load, to_csv_block
from .probe_clean import PROMPT, SYSTEM, bootstrap_diff, norm, parse, score_chunk, IDENTITY

NEAR = RAW / "_near"
OUT = Path(os.environ.get("CORE_NEAR_DIR", ARCHIVE / "near")).resolve()
SEED = 0
K = 20            # rows per chunk
PER_CHUNK = 3     # target entities per chunk
# Hospital has 45 hospitals and a support-1 chunk needs 17 filler hospitals besides its targets,
# so 24 is its ceiling. Pilot (09-29) used beers 24 / movies 30; kept in data/raw/_near_pilot.
N_TARGETS = {"hospital": 24, "beers": 48, "movies": 60}
SUPPORTS = {"hospital": (1, 3), "beers": (1, 3), "movies": (1,)}
TYPES = ("real", "near", "control")
PROMPTS = ("standard", "evidence")
EVIDENCE_PROMPT = PROMPT.replace(
    "Reply with JSON:",
    "Base every correction on evidence within this table only. Do not change a value just because "
    "it disagrees with what you know about real-world entities.\nReply with JSON:")
BASE = {"hospital": "hospital_surrogate", "beers": "beers_surrogate", "movies": "movies_surrogate"}
KEY = {"hospital": "ProviderNumber", "beers": "brewery_id", "movies": "Id"}
NAME = {"hospital": "HospitalName", "beers": "brewery-name", "movies": "Name"}
# cells watched for knowledge-driven edits (all set by the builder, identical across versions
# except the name)
WATCH = {"hospital": ["HospitalName", "City", "State", "ZipCode", "CountyName"],
         "beers": ["brewery-name", "city", "state"], "movies": ["Name", "Director", "Year"]}

# Flagship hospitals with a single, unambiguous campus; their location comes from CMS.
HOSPITALS = """MAYO CLINIC HOSPITAL ROCHESTER|JOHNS HOPKINS HOSPITAL, THE|MASSACHUSETTS GENERAL HOSPITAL|
CEDARS-SINAI MEDICAL CENTER|UCSF MEDICAL CENTER|RONALD REAGAN UCLA MEDICAL CENTER|STANFORD HEALTH CARE|
NORTHWESTERN MEMORIAL HOSPITAL|BRIGHAM AND WOMEN'S HOSPITAL|MOUNT SINAI HOSPITAL|NYU LANGONE HOSPITALS|
HOUSTON METHODIST HOSPITAL|BARNES JEWISH HOSPITAL|DUKE UNIVERSITY HOSPITAL|VANDERBILT UNIVERSITY MEDICAL CENTER|
UNIVERSITY OF MICHIGAN HEALTH SYSTEM|RUSH UNIVERSITY MEDICAL CENTER|KECK HOSPITAL OF USC|
THE UNIVERSITY OF CHICAGO MEDICAL CENTER|YALE-NEW HAVEN HOSPITAL|EMORY UNIVERSITY HOSPITAL|TAMPA GENERAL HOSPITAL|
BAYLOR UNIVERSITY MEDICAL CENTER|BELLEVUE HOSPITAL CENTER|BETH ISRAEL DEACONESS MEDICAL CENTER|TUFTS MEDICAL CENTER|
INTERMOUNTAIN MEDICAL CENTER|CHILDREN'S HOSPITAL OF PHILADELPHIA|BOSTON CHILDREN'S HOSPITAL|
ST JUDE CHILDRENS RESEARCH HOSPITAL|TEXAS CHILDRENS HOSPITAL|HACKENSACK UNIVERSITY MEDICAL CENTER|
UNIVERSITY OF IOWA HOSPITAL & CLINICS|UNIVERSITY OF ALABAMA HOSPITAL|HUNTSVILLE HOSPITAL|GEISINGER MEDICAL CENTER|
MEDSTAR GEORGETOWN UNIVERSITY HOSPITAL|GEORGE WASHINGTON UNIV HOSPITAL|UPMC PRESBYTERIAN SHADYSIDE|
SCRIPPS MERCY HOSPITAL|MAINEHEALTH MAINE MEDICAL CENTER|LENOX HILL HOSPITAL|HOSPITAL FOR SPECIAL SURGERY|
HARBORVIEW MEDICAL CENTER|UNIVERSITY OF KANSAS HOSPITAL|OHIO STATE UNIVERSITY HOSPITALS|
UNIVERSITY OF WASHINGTON MEDICAL CTR|MOUNT SINAI MEDICAL CENTER|JACKSON HEALTH SYSTEM""".replace("\n", "").split("|")
GENERIC_NAME = set("""hospital hospitals medical center centers ctr university univ health system care clinic
clinics memorial general regional community childrens children's of the and & at for brewing brewery company
co beer ales ale works""".split())


# --------------------------------------------------------------------------- candidates
def cms_general() -> pd.DataFrame:
    return pd.read_csv(RAW / "_cms" / "xubh-q36u.csv", dtype=str, keep_default_na=False)


def candidates_hospital() -> pd.DataFrame:
    g = cms_general()
    g = g[g["Facility Name"].isin(HOSPITALS)].drop_duplicates("Facility Name", keep=False)
    return pd.DataFrame({"name": g["Facility Name"].str.lower(), "city": g["City/Town"].str.lower(),
                         "state": g["State"].str.lower()})


def candidates_beers() -> pd.DataFrame:
    _, full = load("beers")
    b = full[["brewery-name", "city", "state"]].drop_duplicates()
    b = b[~b["brewery-name"].duplicated(keep=False)]  # one location per brewery name
    return b.rename(columns={"brewery-name": "name"}).reset_index(drop=True)


def candidates_movies(top: int = 300) -> pd.DataFrame:
    imdb = RAW / "_imdb"
    r = pd.read_csv(imdb / "title.ratings.tsv.gz", sep="\t", dtype=str)
    r = r[r["numVotes"].astype(int) > 300_000]
    t = pd.concat(ch[ch["tconst"].isin(r["tconst"]) & (ch["titleType"] == "movie")]
                  for ch in pd.read_csv(imdb / "title.basics.tsv.gz", sep="\t", dtype=str,
                                        usecols=["tconst", "titleType", "primaryTitle", "startYear"],
                                        chunksize=1_000_000))
    t = t.merge(r, on="tconst").assign(v=lambda x: x["numVotes"].astype(int)).nlargest(top, "v")
    crew = pd.concat(ch[ch["tconst"].isin(t["tconst"])] for ch in
                     pd.read_csv(imdb / "title.crew.tsv.gz", sep="\t", dtype=str, chunksize=1_000_000))
    t = t.merge(crew[["tconst", "directors"]], on="tconst")
    ids = {n for d in t["directors"] for n in d.split(",")}
    names = {}
    for ch in pd.read_csv(imdb / "name.basics.tsv.gz", sep="\t", dtype=str,
                          usecols=["nconst", "primaryName"], chunksize=2_000_000):
        names.update(dict(ch[ch["nconst"].isin(ids)].values))
    t["director"] = t["directors"].map(lambda d: ",".join(names.get(n, "") for n in d.split(",")))
    t = t[~t["primaryTitle"].duplicated(keep=False)]  # remakes share titles: ambiguous
    return pd.DataFrame({"name": t["primaryTitle"], "year": t["startYear"], "director": t["director"],
                         "tconst": t["tconst"]}).reset_index(drop=True)


CANDIDATES = {"hospital": candidates_hospital, "beers": candidates_beers, "movies": candidates_movies}


# --------------------------------------------------------------------------- screening
def question(ds: str, row: dict) -> str:
    if ds == "movies":
        return f"Who directed the film {row['name']} ({row['year']})? Reply with the director's name only."
    kind = "hospital" if ds == "hospital" else "brewery"
    return (f"In which city and state is the US {kind} \"{row['name']}\" located? "
            f"Reply with 'City, ST' only.")


def place_key(s: str) -> str:
    s = norm(s).replace("saint ", "st ").replace("st. ", "st ").replace("mount ", "mt ")
    return re.sub(r"[^a-z ]", "", s).strip()


def fold(s: str) -> str:
    """Lowercase, accents and punctuation dropped: "Miloš Forman" == "Milos Forman",
    "Bong Joon-ho" == "Bong Joon Ho"."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def correct(ds: str, row: dict, answer: str) -> bool:
    a = norm(answer).strip(" .")
    if ds == "movies":
        # the full name, or a surname of 4+ letters ("The Wachowskis" for Lana/Lilly Wachowski)
        fa = fold(answer)
        return any(d and (fold(d) in fa or (len(fold(d).split()[-1]) >= 4 and fold(d).split()[-1] in fa))
                   for d in row["director"].split(","))
    parts = [p.strip() for p in a.split(",")]
    return len(parts) >= 2 and place_key(parts[0]) == place_key(row["city"]) \
        and parts[-1].strip()[:2] == norm(row["state"])


def screen(ds: str, model: str, plan_only: bool = False) -> pd.DataFrame:
    """Ask the model the question behind each famous entity (where is it / who directed it).
    plan_only: only the entities the built tables use, to learn which of them *this* model knows
    (the tables were built from DeepSeek's screening); saved as screen_plan_<ds>__<model>.csv."""
    if plan_only:
        plan = json.loads((NEAR / ds / "plan.json").read_text())
        cols = ["name", "year", "director", "tconst"] if ds == "movies" else ["name", "city", "state"]
        cand = pd.DataFrame([{c: p["famous"][c] for c in cols} for p in plan["plan"]])
    else:
        cand = pd.read_csv(NEAR / f"candidates_{ds}.csv", dtype=str, keep_default_na=False)
    rows = cand.to_dict("records")
    # GLM-5.3 cannot switch reasoning off and its reasoning tokens count against max_tokens: with
    # 40 it returned empty or cut answers for 2 of 48 breweries, which then counted as unknown
    # (gpt-6.x likewise cannot turn reasoning off; its reasoning tokens count against the budget too)
    budget = 440 if ("glm" in model.lower() or "gpt-6" in model.lower()) else 40
    ask = lambda r: complete(model, question(ds, r), system="Answer briefly.", max_tokens=budget)
    with cf.ThreadPoolExecutor(8) as ex:
        answers = list(ex.map(ask, rows))
    cand["answer"] = answers
    cand["known"] = [correct(ds, r, a) for r, a in zip(rows, answers)]
    tag = model.replace(":", "_").replace("/", "_")
    cand.to_csv(NEAR / f"screen{'_plan' if plan_only else ''}_{ds}__{tag}.csv", index=False)
    return cand


# --------------------------------------------------------------------------- building
def english() -> set[str]:
    return {w.strip().lower() for w in open("/usr/share/dict/words")}


def near_form(name: str, rng: random.Random, taken: set[str]) -> str | None:
    """One vowel of the most distinctive word changed: "anchor" -> "anchir"."""
    # ties in length are broken alphabetically: sorting a set by length alone left the order of
    # equally long words to Python's per-process string hashing, so two builds could differ
    words = sorted({w for w in re.findall(r"[A-Za-z]+", name) if len(w) >= 4 and w.lower() not in GENERIC_NAME},
                   key=lambda w: (-len(w), w))
    for w in words:
        spots = [i for i, ch in enumerate(w) if ch.lower() in "aeiou" and 0 < i < len(w) - 1]
        rng.shuffle(spots)
        for i in spots:
            for v in rng.sample("aeiou", 5):
                if v == w[i].lower():
                    continue
                nw = w[:i] + (v.upper() if w[i].isupper() else v) + w[i + 1:]
                if nw.lower() not in taken:
                    return re.sub(rf"\b{w}\b", nw, name, count=1)
    return None


def fake_facts(ds: str, known: pd.DataFrame, rng: random.Random) -> list[dict]:
    """Other real facts for each known entity: a location it is not in / a director it lacks."""
    out = []
    if ds == "hospital":  # the table is Alabama's: another Alabama city, with its zip and county
        g = cms_general()
        al = g[g["State"] == "AL"][["City/Town", "ZIP Code", "County/Parish"]].drop_duplicates("City/Town")
        places = [tuple(x.lower() for x in p) for p in al.values]
        for r in known.itertuples():
            city, zipc, county = rng.choice([p for p in places if p[0] != r.city])
            out.append({"City": city, "ZipCode": zipc, "CountyName": county, "State": "al"})
    elif ds == "beers":
        _, full = load("beers")
        places = list(full[["city", "state"]].drop_duplicates().itertuples(index=False))
        for r in known.itertuples():
            city, state = rng.choice([p for p in places if p[1] != r.state])
            out.append({"city": city, "state": state})
    else:
        directors = sorted({d for x in known["director"] for d in x.split(",") if d})
        for r in known.itertuples():
            out.append({"Director": rng.choice([d for d in directors if d not in r.director.split(",")]),
                        "Year": r.year})
    return out


def build(ds: str, model: str, reuse_near: str | None = None) -> dict:
    """reuse_near: directory of an earlier build (with <ds>/plan.json) whose near-name forms are
    kept, so a rebuild on a changed base table changes nothing but the base rows."""
    old_near = {}
    if reuse_near:
        old = json.loads((ROOT / reuse_near / ds / "plan.json").read_text())
        old_near = {p["famous"]["name"]: p["near"] for p in old["plan"]}
    rng = random.Random(SEED)
    tag = model.replace(":", "_").replace("/", "_")
    known = pd.read_csv(NEAR / f"screen_{ds}__{tag}.csv", dtype=str, keep_default_na=False)
    known = known[known["known"] == "True"]
    if ds != "movies":  # "Anchorage Brewing Company": the city is readable off the name, not knowledge
        known = known[[place_key(c) not in place_key(n) for c, n in zip(known["city"], known["name"])]]
    known = known.reset_index(drop=True)
    dirty, clean = load(BASE[ds])
    key, name_col = KEY[ds], NAME[ds]
    # Target entities need enough rows whose watched cells are all correct: only those rows go
    # into chunks (every row of the entity is rewritten, so the table stays consistent).
    watch_err = (dirty[WATCH[ds]] != clean[WATCH[ds]]).any(axis=1)
    rows_of = {k: list(g.index) for k, g in clean.groupby(key, sort=False)}
    ok_rows = {k: [i for i in rs if not watch_err[i]] for k, rs in rows_of.items()}
    need = max(SUPPORTS[ds])
    eligible = [k for k, rs in ok_rows.items() if len(rs) >= need]
    n = min(N_TARGETS[ds], len(eligible), len(known))
    n -= n % PER_CHUNK
    targets = rng.sample(eligible, n)
    taken = english() | {w.lower() for v in known["name"] for w in re.findall(r"[A-Za-z]+", v)}
    famous = known.sample(n=n, random_state=SEED).to_dict("records")
    facts = fake_facts(ds, pd.DataFrame(famous), rng)
    plan = []
    for k, f, fk in zip(targets, famous, facts):
        near = near_form(f["name"], rng, taken)   # always drawn, so the random stream is the same
        near = old_near.get(f["name"], near)
        plan.append({"key": k, "rows": ok_rows[k], "all_rows": rows_of[k], "surrogate": clean.at[ok_rows[k][0], name_col],
                     "famous": f, "near": near, "facts": fk})
    plan = [p for p in plan if p["near"]]
    plan = plan[: len(plan) - len(plan) % PER_CHUNK]
    # chunks: PER_CHUNK targets + fillers, one row each from distinct non-target entities
    others = [k for k in rows_of if k not in {p["key"] for p in plan}]
    chunks = {}
    for s in SUPPORTS[ds]:
        cs = []
        for c in range(0, len(plan), PER_CHUNK):
            crng = random.Random(f"{SEED}-{s}-{c}")
            rows = [r for p in plan[c:c + PER_CHUNK] for r in p["rows"][:s]]
            fillers = crng.sample(others, K - len(rows))
            rows += [crng.choice(rows_of[f]) for f in fillers]
            crng.shuffle(rows)
            cs.append(rows)
        chunks[str(s)] = cs
    # tables per type: facts set in every version; only the name differs
    for typ in TYPES:
        d, c = dirty.copy(), clean.copy()
        for p in plan:
            name = {"real": p["famous"]["name"], "near": p["near"], "control": p["surrogate"]}[typ]
            for i in p["all_rows"]:
                for col, v in {name_col: name, **p["facts"]}.items():
                    # a watched cell that was an error keeps being one (dirty differs from clean);
                    # such rows never enter a chunk
                    erroneous = dirty.at[i, col] != clean.at[i, col]
                    c.at[i, col] = v
                    d.at[i, col] = (v + " x") if erroneous else v
                if ds == "movies":
                    # The surrogate director often also appears among the film's writers or cast;
                    # left there, it let the model "repair" the new director back from the Creator
                    # column (pilot, evidence prompt). Replace it everywhere in the row.
                    old = set(clean.at[i, "Director"].split(","))
                    for col in ("Creator", "Actors"):
                        for t in (c, d):
                            t.at[i, col] = ",".join(p["facts"]["Director"] if x in old else x
                                                    for x in t.at[i, col].split(","))
        out = NEAR / ds / typ
        out.mkdir(parents=True, exist_ok=True)
        c.to_csv(out / "clean.csv", index=False)
        d.to_csv(out / "dirty.csv", index=False)
    info = {"dataset": ds, "base": BASE[ds], "screened_by": model, "known": len(known),
            "targets": len(plan), "chunks": {s: len(v) for s, v in chunks.items()},
            "plan": plan, "chunk_rows": chunks}
    (NEAR / ds / "plan.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))
    return {k: v for k, v in info.items() if k not in ("plan", "chunk_rows")}


# --------------------------------------------------------------------------- running
def run(ds: str, model: str, workers: int = 4, max_tokens: int = 4096) -> None:
    plan = json.loads((NEAR / ds / "plan.json").read_text())
    tag = model.replace(":", "_").replace("/", "_")
    jobs = []
    for typ in TYPES:
        dirty = pd.read_csv(NEAR / ds / typ / "dirty.csv", dtype=str, keep_default_na=False)
        for s, cs in plan["chunk_rows"].items():
            for pr in PROMPTS:
                for ci, rows in enumerate(cs):
                    shown = dirty.iloc[rows].reset_index(drop=True)
                    shown.insert(0, "_row", range(1, len(rows) + 1))
                    text = (PROMPT if pr == "standard" else EVIDENCE_PROMPT).format(block=to_csv_block(shown))
                    jobs.append(((typ, s, pr, ci), text))
    with cf.ThreadPoolExecutor(workers) as ex:
        outs = list(ex.map(lambda j: complete_json(model, j[1], system=SYSTEM, max_tokens=max_tokens), jobs))
    res = [{"type": t, "support": s, "prompt": p, "chunk": c, "output": o} for ((t, s, p, c), _), o in zip(jobs, outs)]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{tag}__{ds}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"{ds}: {len(res)} calls")


# --------------------------------------------------------------------------- analysis
def analyze(ds: str, model: str) -> dict:
    known = known_names(ds, model)
    plan = json.loads((NEAR / ds / "plan.json").read_text())
    tag = model.replace(":", "_").replace("/", "_")
    res = json.loads((OUT / f"{tag}__{ds}.json").read_text())
    tables = {t: load(f"_near/{ds}/{t}") for t in TYPES}
    target_rows = {i: p for p in plan["plan"] for i in p["rows"]}
    ident = IDENTITY[ds]
    per = collections.defaultdict(lambda: collections.defaultdict(list))  # setting -> entity -> flags
    repair = collections.defaultdict(list)
    by_col = collections.defaultdict(lambda: collections.defaultdict(list))
    examples = collections.defaultdict(list)
    for r in res:
        rows = plan["chunk_rows"][r["support"]][r["chunk"]]
        dirty, clean = (x.iloc[rows].reset_index(drop=True) for x in tables[r["type"]])
        preds = parse(r["output"])
        setting = (r["type"], r["support"], r["prompt"])
        # repair quality on the non-target part of the chunk
        keep = [j for j, i in enumerate(rows) if i not in target_rows]
        repair[setting].append({"counts": score_chunk(dirty.iloc[keep].reset_index(drop=True),
                                                      clean.iloc[keep].reset_index(drop=True),
                                                      [dict(p, row=keep.index(int(p["row"]) - 1) + 1) for p in preds
                                                       if str(p.get("row", "")).isdigit() and int(p["row"]) - 1 in keep],
                                                      ident)})
        edits = {}
        for p in preds:
            try:
                j = int(p["row"]) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= j < len(rows) and rows[j] in target_rows:
                edits[(j, str(p["column"]))] = str(p["value"]).strip()
        for j, i in enumerate(rows):
            if i not in target_rows:
                continue
            ent = target_rows[i]
            truth = ent["famous"]
            for col in WATCH[ds]:
                v = edits.get((j, col))
                changed = v is not None and norm(v) != norm(clean.at[j, col])
                to_fact = changed and _is_fact(ds, col, v, truth)
                per[setting][ent["key"]].append((changed, to_fact))
                by_col[setting][col].append((changed, to_fact))
                if changed and len(examples[setting]) < 8:
                    examples[setting].append({"col": col, "table": clean.at[j, col], "model": v,
                                              "famous": truth["name"]})
    summary = {}
    for setting, ents in sorted(per.items()):
        cells = [f for fl in ents.values() for f in fl]
        summary["|".join(setting)] = {
            "entities": len(ents), "cells": len(cells),
            "edit_rate": sum(c for c, _ in cells) / len(cells),
            "to_fact_rate": sum(t for _, t in cells) / len(cells),
            "entities_edited": sum(any(c for c, _ in fl) for fl in ents.values()),
            "repair_f1_other_rows": _f1(repair[setting]),
            "by_column": {c: {"cells": len(v), "edit_rate": round(sum(x for x, _ in v) / len(v), 3),
                              "to_fact_rate": round(sum(t for _, t in v) / len(v), 3)}
                          for c, v in by_col[setting].items()},
            "examples": examples[setting]}
    summary["key_rates"] = key_rates(ds, model)
    if known is not None:  # the same rates over the target entities this model itself knows
        summary["screened_known"] = {"known": len(known), "targets": len(plan["plan"])}
        summary["key_rates_known"] = key_rates(ds, model, only_known=True)
    (OUT / f"{tag}__{ds}__summary.json").write_text(json.dumps(summary, indent=1))
    return summary


# The cell each type is about: where the table contradicts the famous entity (type real), or
# the near name itself (type near).
KEY_COLUMN = {("hospital", "real"): "City", ("beers", "real"): "city", ("movies", "real"): "Director",
              ("hospital", "near"): "HospitalName", ("beers", "near"): "brewery-name", ("movies", "near"): "Name"}


def known_names(ds: str, model: str) -> set[str]:
    """Required plan-only screening; missing inputs must never select all targets."""
    from .screening import known_names as checked_names
    return checked_names(NEAR, ds, model)


def key_rates(ds: str, model: str, n_boot: int = 2000, only_known: bool = False) -> dict:
    """Share of target entities' key cells rewritten to the famous entity's fact, per setting,
    with a 95% bootstrap interval over entities; the control uses the same column as "real"."""
    import random
    keep = known_names(ds, model) if only_known else None
    plan = json.loads((NEAR / ds / "plan.json").read_text())
    tag = model.replace(":", "_").replace("/", "_")
    res = json.loads((OUT / f"{tag}__{ds}.json").read_text())
    tables = {t: load(f"_near/{ds}/{t}")[1] for t in TYPES}
    target = {i: p for p in plan["plan"] for i in p["rows"] if keep is None or p["famous"]["name"] in keep}
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in res:
        col = KEY_COLUMN[(ds, "real" if r["type"] == "control" else r["type"])]
        rows = plan["chunk_rows"][r["support"]][r["chunk"]]
        edits = {}
        for p in parse(r["output"]):
            try:
                edits[(int(p["row"]) - 1, str(p["column"]))] = str(p["value"])
            except (TypeError, ValueError):
                continue
        for j, i in enumerate(rows):
            if i in target:
                v = edits.get((j, col))
                hit = v is not None and norm(v) != norm(tables[r["type"]].at[i, col]) \
                    and _is_fact(ds, col, v, target[i]["famous"])
                per[(r["type"], r["support"], r["prompt"])][target[i]["key"]].append(hit)
    out = {}
    for k, ents in sorted(per.items()):
        m = [sum(v) / len(v) for v in ents.values()]
        rng = random.Random(0)
        bs = sorted(sum(rng.choice(m) for _ in m) / len(m) for _ in range(n_boot))
        out["|".join(k)] = {"rate": round(sum(m) / len(m), 3), "ci": [round(bs[int(0.025 * n_boot)], 3),
                                                                  round(bs[int(0.975 * n_boot) - 1], 3)],
                           "entities": len(m)}
    return out


def _is_fact(ds: str, col: str, v: str, truth: dict) -> bool:
    """Did the edit write the famous entity's real fact (or name) into the cell?"""
    if col == NAME[ds]:
        return norm(v) == norm(truth["name"])
    if ds == "movies":
        return col == "Director" and any(d and norm(d) in norm(v) for d in truth["director"].split(","))
    field = {"City": "city", "city": "city", "State": "state", "state": "state"}.get(col)
    return bool(field) and place_key(v) == place_key(truth[field])


def _f1(chunks: list[dict]) -> float:
    from .probe_clean import f1_of
    return round(f1_of(chunks, "all"), 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["candidates", "screen", "rescore", "build", "run", "analyze"])
    ap.add_argument("--dataset", nargs="*", default=["hospital", "beers", "movies"])
    ap.add_argument("--model", default="custom:deepseek/deepseek-v4-pro")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--plan-only", action="store_true", help="screen only the entities the tables use")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--reuse-near", help="build: keep the near-name forms of an earlier build, e.g. data/raw/_surrogate_v1/_near")
    a = ap.parse_args()
    NEAR.mkdir(parents=True, exist_ok=True)
    for ds in a.dataset:
        if a.cmd == "candidates":
            c = CANDIDATES[ds]()
            c.to_csv(NEAR / f"candidates_{ds}.csv", index=False)
            print(ds, len(c), "candidates")
        elif a.cmd == "rescore":  # re-judge saved plan-only screening answers (no model calls)
            for f in sorted(NEAR.glob(f"screen_plan_{ds}__*.csv")):
                c = pd.read_csv(f, dtype=str, keep_default_na=False)
                c["known"] = [correct(ds, r, r["answer"]) for r in c.to_dict("records")]
                c.to_csv(f, index=False)
                print(f.name, f"{int(c['known'].sum())}/{len(c)} known")
        elif a.cmd == "screen":
            c = screen(ds, a.model, a.plan_only)
            print(ds, f"{int(c['known'].sum())}/{len(c)} known")
        elif a.cmd == "build":
            print(json.dumps(build(ds, a.model, a.reuse_near), ensure_ascii=False))
        elif a.cmd == "run":
            run(ds, a.model, a.workers, a.max_tokens)
        else:
            print(ds, json.dumps(analyze(ds, a.model), indent=1))


if __name__ == "__main__":
    main()
