"""Build the three CoRe conditions for Hospital: original / fresh / surrogate.

- original:  data/raw/hospital (Raha/Baran benchmark), untouched.
- fresh:     current CMS Hospital Compare release (Timely and Effective Care + Hospital
             General Information), reshaped to the original 20 columns and dirtied with the
             original's error profile. Same public source, published after model cutoffs.
- surrogate: the original with every identity value (provider number, name, address, city,
             zip, county, phone) replaced by a consistent fictitious one, errors moved along.

Usage:
  .venv/bin/python -m src.hospital_variants profile      # error profile of the original
  .venv/bin/python -m src.hospital_variants fresh        # download CMS data, build fresh
  .venv/bin/python -m src.hospital_variants fresh-errors # redraw the fresh table's errors (v2)
  .venv/bin/python -m src.hospital_variants surrogate    # build surrogate
Outputs: data/raw/hospital_fresh/{dirty,clean}.csv, data/raw/hospital_surrogate/{dirty,clean}.csv
Add "--seed N" to fresh / surrogate / surrogate-words for another construction seed: the table
goes to data/raw/<name>_sN. A seed redraws everything random in the construction: the fresh
table's error cells and characters; a surrogate's fictitious values and error characters.
"""
import collections
import json
import os
import random
import sys
from pathlib import Path
import urllib.request

import pandas as pd

from .data import RAW, load

META = "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{}"
TIMELY_EFFECTIVE, GENERAL_INFO = "yv7e-xc69", "xubh-q36u"
CACHE = RAW / "_cms"
IDENTITY = ["ProviderNumber", "HospitalName", "Address1", "City", "ZipCode", "CountyName", "PhoneNumber"]


# --------------------------------------------------------------------------- error profile
def profile(dirty: pd.DataFrame, clean: pd.DataFrame) -> dict:
    """Per-column error rate and how errors look. In Hospital almost every error replaces
    one or more characters with 'x' (birmingham -> birmingxam)."""
    prof = {}
    for c in clean.columns:
        diff = [(d, t) for d, t in zip(dirty[c], clean[c]) if d != t]
        kinds, nsub = collections.Counter(), collections.Counter()
        for d, t in diff:
            if len(d) == len(t) and all(a == b or a == "x" for a, b in zip(d, t)):
                kinds["x_sub"] += 1
                nsub[sum(a != b for a, b in zip(d, t))] += 1
            elif d == "":
                kinds["emptied"] += 1
            else:
                kinds["other"] += 1
        prof[c] = {"rate": len(diff) / len(clean), "kinds": dict(kinds), "x_chars": dict(nsub)}
    return prof


def x_substitute(value: str, rng: random.Random, p_all: float = 0.96) -> str:
    """The original benchmark's error: pick one character of the value and turn its
    occurrences into 'x' -- all of them in 96% of the original's cells (birmingham ->
    birmingxam, "pneumonia patients" -> "pneumonix pxtients"), only some in the rest."""
    candidates = sorted({ch for ch in value if ch != "x"})
    if not candidates:
        return value
    ch = rng.choice(candidates)
    idx = [i for i, c in enumerate(value) if c == ch]
    if len(idx) > 1 and rng.random() > p_all:
        idx = rng.sample(idx, rng.randint(1, len(idx) - 1))
    chars = list(value)
    for i in idx:
        chars[i] = "x"
    return "".join(chars)


def x_substitute_weighted(value: str, rng: random.Random, p_all: float = 0.96) -> str:
    """x_substitute with the original's choice of character. x_substitute draws among the
    value's distinct characters; the original draws a position, so characters that occur more
    often are hit more often: its replaced character occurs 1.88 times in the value on average
    (a position draw predicts 1.89, a distinct-character draw 1.52). With the distinct-character
    draw the fresh table's errors were lighter than the original's (1.60)."""
    positions = [i for i, c in enumerate(value) if c != "x"]
    if not positions:
        return value
    ch = value[rng.choice(positions)]
    idx = [i for i, c in enumerate(value) if c == ch]
    if len(idx) > 1 and rng.random() > p_all:
        idx = rng.sample(idx, rng.randint(1, len(idx) - 1))
    chars = list(value)
    for i in idx:
        chars[i] = "x"
    return "".join(chars)


def reweight(dirty: pd.DataFrame, clean: pd.DataFrame, seed: int = 0, cols: list[str] | None = None) -> pd.DataFrame:
    """Redraw x-substitution errors (in `cols`, default all columns) with the original's
    position-weighted choice. The error cells stay where they are (as in the first builds,
    archived in data/raw/_fresh_v1 and _surrogate_v1); only which character turns into 'x'
    changes."""
    rng = random.Random(seed + 101)
    out = dirty.copy()
    for j in range(clean.shape[1]):
        if cols is not None and clean.columns[j] not in cols:
            continue
        for r in range(len(clean)):
            d, c = dirty.iat[r, j], clean.iat[r, j]
            if d != c and d != "":
                new = x_substitute_weighted(c, rng)
                out.iat[r, j] = new if new != c else d
    return out


def inject(clean: pd.DataFrame, prof: dict, seed: int = 0) -> pd.DataFrame:
    """Dirty `clean` so each column gets the original's error rate and error kinds."""
    rng = random.Random(seed)
    dirty = clean.copy()
    for j, c in enumerate(clean.columns):
        p = prof.get(c)
        if not p or p["rate"] == 0:
            continue
        kinds, kw = list(p["kinds"]), list(p["kinds"].values())
        for r in rng.sample(range(len(clean)), round(p["rate"] * len(clean))):
            v = clean.iat[r, j]
            if rng.choices(kinds, kw)[0] == "emptied":
                dirty.iat[r, j] = ""
            else:  # x_sub (and the rare "other") -> x-substitution
                dirty.iat[r, j] = x_substitute(v, rng)
    return dirty


# --------------------------------------------------------------------------- fresh data
def fetch(dataset_id: str) -> tuple[pd.DataFrame, str]:
    """Download a CMS Provider Data Catalog dataset (cached). Returns (frame, release date)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    meta_path = CACHE / f"{dataset_id}.json"
    if not meta_path.exists():
        with urllib.request.urlopen(META.format(dataset_id), timeout=60) as r:
            meta_path.write_bytes(r.read())
    meta = json.loads(meta_path.read_text())
    url = meta["distribution"][0]["downloadURL"]
    csv_path = CACHE / f"{dataset_id}.csv"
    if not csv_path.exists():
        with urllib.request.urlopen(url, timeout=300) as r:
            csv_path.write_bytes(r.read())
    return pd.read_csv(csv_path, dtype=str, keep_default_na=False), meta.get("modified", "")


def build_fresh(n_rows: int = 1000, seed: int = 0) -> dict:
    te, te_date = fetch(TIMELY_EFFECTIVE)
    gi, gi_date = fetch(GENERAL_INFO)
    gi = gi[["Facility ID", "Hospital Type", "Hospital Ownership", "Emergency Services"]]
    df = te.merge(gi, on="Facility ID", how="left").fillna("")
    low = lambda s: s.str.lower().str.strip()
    score = df["Score"].where(~df["Score"].isin(["Not Available", ""]), "empty")
    sample = df["Sample"].where(~df["Sample"].isin(["Not Available", ""]), "0")
    out = pd.DataFrame({
        "index": "",
        "ProviderNumber": df["Facility ID"].str.lstrip("0"),  # original drops the leading 0
        "HospitalName": low(df["Facility Name"]),
        "Address1": low(df["Address"]),
        "Address2": "empty",
        "Address3": "empty",
        "City": low(df["City/Town"]),
        "State": low(df["State"]),
        "ZipCode": df["ZIP Code"].str[:5],
        "CountyName": low(df["County/Parish"]),
        "PhoneNumber": df["Telephone Number"].str.replace(r"\D", "", regex=True),
        "HospitalType": low(df["Hospital Type"]),
        "HospitalOwner": low(df["Hospital Ownership"]),
        "EmergencyService": low(df["Emergency Services"]),
        "Condition": low(df["Condition"]),
        "MeasureCode": low(df["Measure ID"]),
        "MeasureName": low(df["Measure Name"]),
        "Score": low(score),
        "Sample": sample + " patients",
        "Stateavg": low(df["State"]) + "_" + low(df["Measure ID"]),
    })
    # Keep the original's shape: whole hospitals in provider order, starting with the
    # hospitals the original benchmark covers (same entities, new release -> new values).
    odirty, oclean = load("hospital")
    known = set(oclean["ProviderNumber"])
    order = list(out["ProviderNumber"].drop_duplicates())
    order = [p for p in order if p in known] + [p for p in order if p not in known]
    groups = dict(tuple(out.groupby("ProviderNumber", sort=False)))
    rows, total = [], 0
    for p in order:
        rows.append(groups[p])
        total += len(groups[p])
        if total >= n_rows:
            break
    clean = pd.concat(rows).iloc[:n_rows].reset_index(drop=True)
    clean["index"] = [str(i + 1) for i in range(len(clean))]
    prof = profile(odirty, oclean)
    prof["index"] = {"rate": 0, "kinds": {}, "x_chars": {}}
    dirty = reweight(inject(clean, prof, seed), clean, seed)
    save("hospital_fresh", dirty, clean)
    info = {"timely_effective_release": te_date, "general_info_release": gi_date,
            "rows": len(clean), "hospitals": int(clean["ProviderNumber"].nunique()),
            "hospitals_shared_with_original": len(set(clean["ProviderNumber"]) & known),
            "measures": sorted(clean["MeasureCode"].unique())[:40],
            "error_cells": int((dirty != clean).sum().sum()),
            "original_error_cells": int((odirty != oclean).sum().sum()),
            "errors": "v2 (09-30): replaced character drawn by position, as in the original"}
    (RAW / "hospital_fresh" / "provenance.json").write_text(json.dumps(info, indent=1))
    return info


def seeded(name: str, seed: int) -> str:
    """Table name for a construction seed: seed 0 is the main table, others get a suffix."""
    return name if seed == 0 else f"{name}_s{seed}"


def out_dir(name: str) -> Path:
    """Where a built table goes: data/raw/<name>, or $CORE_BUILD_DIR/<name> when set (used to
    rebuild a table elsewhere and compare it with the one on disk)."""
    d = Path(os.environ.get("CORE_BUILD_DIR") or RAW) / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def fresh_dirty(clean: pd.DataFrame, seed: int) -> pd.DataFrame:
    """The fresh table's errors for one seed: error cells drawn with the original's per-column
    rates, characters drawn by position."""
    odirty, oclean = load("hospital")
    prof = profile(odirty, oclean)
    prof["index"] = {"rate": 0, "kinds": {}, "x_chars": {}}
    return reweight(inject(clean, prof, seed), clean, seed)


def build_fresh_seed(seed: int) -> dict:
    """The fresh table with another error seed (same CMS rows as the main fresh table)."""
    _, clean = load("hospital_fresh")
    dirty = fresh_dirty(clean, seed)
    name = seeded("hospital_fresh", seed)
    save(name, dirty, clean)
    info = {"seed": seed, "rows": len(clean), "error_cells": int((dirty != clean).sum().sum()),
            "note": "same clean table as hospital_fresh; errors redrawn with this seed"}
    (out_dir(name) / "provenance.json").write_text(json.dumps(info, indent=1))
    return info


def reweight_fresh() -> dict:
    """Second build of the fresh table's errors without downloading CMS data again: same clean
    table, same error cells, position-weighted characters."""
    dirty, clean = load("hospital_fresh")
    new = reweight(dirty, clean)
    clean_raw = pd.read_csv(RAW / "hospital_fresh" / "clean.csv", dtype=str, keep_default_na=False)
    new.columns = pd.read_csv(RAW / "hospital_fresh" / "dirty.csv", dtype=str, keep_default_na=False, nrows=0).columns
    new.to_csv(RAW / "hospital_fresh" / "dirty.csv", index=False)
    info = json.loads((RAW / "hospital_fresh" / "provenance.json").read_text())
    info["errors"] = "v2 (09-30): replaced character drawn by position, as in the original"
    info["error_cells"] = int((new.values != clean_raw.values).sum())
    (RAW / "hospital_fresh" / "provenance.json").write_text(json.dumps(info, indent=1))
    return info


# --------------------------------------------------------------------------- surrogate
SYL = ["ba", "vel", "mor", "tas", "quen", "dri", "lo", "fen", "zar", "pim", "rho", "sul",
       "tor", "wex", "ny", "cal", "brin", "osk", "ula", "gar", "hep", "jou", "kel", "vas"]


# Real English words for the "words" surrogate: names are spelled like ordinary English (so
# spelling knowledge still helps) but name no real hospital, which isolates entity knowledge.
WORDS = ["oak", "maple", "cedar", "willow", "birch", "pine", "river", "lake", "meadow", "valley",
         "ridge", "spring", "stone", "silver", "golden", "green", "clear", "bright", "harbor",
         "summit", "hollow", "grove", "creek", "prairie", "sunset", "eagle", "hawk", "glen",
         "heather", "amber", "crystal", "laurel", "forest", "field", "brook", "canyon", "shadow",
         "pleasant", "orchard", "garden", "mill", "bridge", "haven", "copper", "iron", "rose",
         "timber", "juniper", "aspen", "falcon", "lantern", "harvest", "morning", "evening",
         "quiet", "gentle", "noble", "liberty", "unity", "hope", "grace", "beacon", "anchor"]


def pseudo_word(rng: random.Random, n: int = 3) -> str:
    return "".join(rng.choice(SYL) for _ in range(n))


def english_name(rng: random.Random, n: int = 2) -> str:
    return " ".join(rng.sample(WORDS, n))


def surrogate_value(col: str, rng: random.Random, style: str = "pseudo") -> str:
    """A fictitious value of the same kind as the column's real values. style="pseudo" uses
    meaningless syllables (hepmormor); style="words" uses real English words (cedar hollow)."""
    name = (lambda n: english_name(rng, n)) if style == "words" else (lambda n: pseudo_word(rng, n + 1))
    if style == "words" and col == "Address1":
        kind = rng.choice(["street", "avenue", "road", "drive", "blvd"])
        return f"{rng.randint(10, 9999)} {english_name(rng, 1)} {kind}"
    if style == "words" and col == "HospitalName":
        suffix = rng.choice(["medical center", "regional hospital", "memorial hospital", "health center"])
        return f"{name(2)} {suffix}"
    if style == "words" and col in ("City", "CountyName"):
        return name(rng.choice([1, 2]))
    if col == "ProviderNumber":
        return str(rng.randint(90000, 99999))
    if col == "ZipCode":
        return f"{rng.randint(0, 99999):05d}"
    if col == "PhoneNumber":
        return str(rng.randint(2000000000, 9999999999))
    if col == "Address1":
        kind = rng.choice(["street", "avenue", "road", "drive", "blvd"])
        return f"{rng.randint(10, 9999)} {pseudo_word(rng, 2)} {kind}"
    if col == "HospitalName":
        suffix = rng.choice(["medical center", "regional hospital", "memorial hospital", "health center"])
        return f"{pseudo_word(rng)} {suffix}"
    return pseudo_word(rng, rng.choice([2, 3]))  # City, CountyName


def move_error(dirty_v: str, new_clean: str, rng: random.Random) -> str:
    """Give the surrogate value an error of the same kind the original cell had."""
    if dirty_v == "":
        return ""
    out = x_substitute(new_clean, rng)
    return out if out != new_clean else new_clean + "x"


def build_surrogate(seed: int = 0, style: str = "pseudo") -> dict:
    dirty, clean = load("hospital")
    rng = random.Random(seed)
    mapping = {}
    for c in IDENTITY:
        used, mapping[c] = set(clean[c]), {}
        for v in clean[c].drop_duplicates():
            new = surrogate_value(c, rng, style)
            while new in used:  # never collide with a real value in the table
                new = surrogate_value(c, rng, style)
            used.add(new)
            mapping[c][v] = new
    sclean, sdirty = clean.copy(), dirty.copy()
    for c in IDENTITY:
        sclean[c] = clean[c].map(mapping[c])
        sdirty[c] = [mapping[c][cv] if dv == cv else move_error(dv, mapping[c][cv], rng)
                     for cv, dv in zip(clean[c], dirty[c])]
    # v2 (09-30): identity errors redrawn with the original's position-weighted character
    # choice; move_error's distinct-character draw made them lighter than the original's
    # (1.3-1.4 characters changed per identity error against the original's 1.7).
    sdirty = reweight(sdirty, sclean, seed + (1 if style == "words" else 2), IDENTITY)
    # Every other column keeps its values: they carry no hospital identity.
    name = seeded("hospital_surrogate" if style == "pseudo" else "hospital_surrogatewords", seed)
    save(name, sdirty, sclean)
    info = {"style": style, "seed": seed, "replaced_columns": IDENTITY,
            "error_cells": int((sdirty != sclean).sum().sum()),
            "original_error_cells": int((dirty != clean).sum().sum()),
            "same_error_cells_as_original": bool(((sdirty != sclean).values == (dirty != clean).values).all()),
            "errors": "v2 (09-30): replaced character drawn by position, as in the original"}
    (out_dir(name) / "provenance.json").write_text(json.dumps(info, indent=1))
    return info


def save(name: str, dirty: pd.DataFrame, clean: pd.DataFrame) -> None:
    d = out_dir(name)
    clean.to_csv(d / "clean.csv", index=False)
    dirty.to_csv(d / "dirty.csv", index=False)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "profile"
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 0
    if cmd == "profile":
        d, c = load("hospital")
        print(json.dumps({k: v for k, v in profile(d, c).items() if v["rate"]}, indent=1))
    elif cmd == "fresh" and seed:
        print(json.dumps(build_fresh_seed(seed), indent=1))
    elif cmd == "fresh":
        print(json.dumps(build_fresh(), indent=1))
    elif cmd == "fresh-errors":
        print(json.dumps(reweight_fresh(), indent=1))
    elif cmd == "surrogate":
        print(json.dumps(build_surrogate(seed=seed), indent=1))
    elif cmd == "surrogate-words":
        print(json.dumps(build_surrogate(seed=seed, style="words"), indent=1))
