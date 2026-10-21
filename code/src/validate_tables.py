"""Acceptance checks for the constructed tables, to run BEFORE any model sees them.

The fresh table and the two surrogates of Hospital and Movies are built by code, and the first
builds were only checked for how many errors they had: their errors turned out to be of other
kinds (Movies people columns) and lighter (Hospital) than the original's, which was found after
eight models had been run. This script compares every constructed table with the original:

  surrogates  same shape; error cells in the same places; every non-identity cell (clean and
              dirty) identical to the original's; one fictitious value per real value and back;
              no fictitious value that is also a real one; the kinds of identity errors
  fresh       same shape; the original's number of errors per column (Hospital) or per kind
              (Movies); people errors only in Rotten Tomatoes rows; same clean table for all seeds
  all         error strength (Hospital: characters changed per identity error)
  --rebuild   build every table again in a scratch directory under two different
              PYTHONHASHSEED values and compare the files byte for byte with those on disk

Usage: .venv/bin/python -m src.validate_tables [--seeds 0 1 2] [--rebuild]
Exit status 1 if a hard check fails. Report: results/validate_tables.json
"""
import argparse
import collections
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import unicodedata

from .data import BUILD, RAW, ROOT, load
from .hospital_variants import IDENTITY as H_ID
from .hospital_variants import fresh_dirty, seeded
from .movies_variants import IDENTITY as M_ID
from .movies_variants import ErrorModel, _fold, _names, subset, transfer_genres, transfer_names, transfer_people

PEOPLE = ["Director", "Creator", "Actors"]
_SUFFIX = re.compile(r"\s*\((?:[IVX]+)\)$")


def people_kind(d: str, g: str) -> str:
    nd, ng = _names(d), _names(g)
    if not nd:
        return "emptied"
    fd, fg = [_fold(x) for x in nd], [_fold(x) for x in ng]
    if sorted(fd) == sorted(fg):
        return "order or spelling"
    ded = list(dict.fromkeys(_fold(_SUFFIX.sub("", x)) for x in nd))
    if any(_SUFFIX.search(x) for x in nd) and sorted(ded) == sorted(fg):
        return "(I) duplicate"
    if set(fg) < set(fd):
        return "extra names"
    if set(fd) < set(fg):
        return "missing names"
    return "names differ"


def kinds(dirty, clean, col) -> dict:
    return dict(sorted(collections.Counter(people_kind(d, g) for d, g in zip(dirty[col], clean[col]) if d != g).items()))


def chars_changed(dirty, clean, cols) -> float:
    k = [sum(a != b for a, b in zip(d, g)) for c in cols for d, g in zip(dirty[c], clean[c]) if d != g and len(d) == len(g)]
    return round(statistics.mean(k), 2) if k else 0.0


def coarse_kind(d: str, c: str) -> str:
    """How a dirty cell differs from its clean cell, in generic terms, for any column."""
    fold = lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode()
    toks = lambda x: set(re.findall(r"[A-Za-z0-9]+", x.lower()))
    if d == "":
        return "emptied"
    if c == "":
        return "filled"
    if d.lower() == c.lower():
        return "case"
    if fold(d) == fold(c):
        return "accent"
    amp = lambda x: re.sub(r"\s*&\s*", " and ", x.lower())
    if amp(d) == amp(c):
        return "and/&"
    if re.sub(r"[^\w]", "", d.lower()) == re.sub(r"[^\w]", "", c.lower()):
        return "punct/space"
    if d.endswith("%") and d[:-1].replace(".", "").isdigit():
        return "percent"
    if d == c + ".0":
        return ".0"
    td, tc = toks(d), toks(c)
    if tc < td:
        return "tokens added"
    if td < tc:
        return "tokens dropped"
    if td & tc:
        return "tokens changed (some kept)"
    if len(d) == len(c) and sum(x != y for x, y in zip(d, c)) <= 2:
        return "1-2 chars substituted"
    return "other"


# Kinds whose share depends on the values, not on how the error is made, with the reason.
KIND_EXEMPT = {("movies", "Genre", "other"):
               "no word shared by the IMDb and RT lists ('Thriller' -> 'Mystery & Suspense'): depends on "
               "which genres a film has; the RT slots are copied row by row"}


def error_kinds(rep: "Report", base: str, table: str, d, c, od, oc, skip=()) -> None:
    """Every column: about the original's number of errors (85-115%), each kind the original has
    3+ times at least half as often, and kinds the original lacks in at most 10% of the errors
    (2 cells at least). Added 10-02, after the fresh and surrogate Name errors (case only; ": The
    Movie" appended) and the fresh Genre errors (a third too few) had passed every other check."""
    for col in oc.columns:
        if col in skip:
            continue
        ko = collections.Counter(coarse_kind(str(x), str(y)) for x, y in zip(od[col], oc[col]) if x != y)
        kt = collections.Counter(coarse_kind(str(x), str(y)) for x, y in zip(d[col], c[col]) if x != y)
        no, nt = sum(ko.values()), sum(kt.values())
        if not no and not nt:
            continue
        bad = []
        if not 0.85 * no <= nt <= 1.15 * no:
            bad.append(f"{nt} errors, original {no}")
        for k, v in ko.items():
            if v >= 3 and kt.get(k, 0) < 0.5 * v:
                if (base, col, k) in KIND_EXEMPT:
                    rep.note(table, f"{col}: {k} {kt.get(k, 0)} vs original {v}, exempt", KIND_EXEMPT[(base, col, k)])
                else:
                    bad.append(f"{k}: {kt.get(k, 0)}, original {v}")
        new = {k: v for k, v in kt.items() if k not in ko}
        if sum(new.values()) > max(2, 0.1 * nt):
            bad.append(f"kinds the original lacks: {new}")
        rep.check(table, f"{col}: error kinds and count as in the original", not bad, "; ".join(bad) or f"{dict(kt)}")


def x_profile(d, c, cols) -> list[float]:
    """Share of error cells with 1, 2 and 3+ characters replaced."""
    n = [sum(x != y for x, y in zip(a, b)) for col in cols for a, b in zip(d[col], c[col]) if a != b and len(a) == len(b)]
    return [round(sum(k == 1 for k in n) / len(n), 3), round(sum(k == 2 for k in n) / len(n), 3),
            round(sum(k >= 3 for k in n) / len(n), 3)] if n else [0, 0, 0]


def hospital_strength(rep: "Report", table: str, d, c, od, oc, groups: dict) -> None:
    """x-substitutions, and how many characters per cell: within 8 points of the original for
    1, 2 and 3+ characters (a mean is moved by the few long cells with 20-30 replacements)."""
    rep.check(table, "every error is an x-substitution (no more exceptions than the original)",
              xsub_violations(d, c) <= xsub_violations(od, oc), f"{xsub_violations(d, c)} vs original {xsub_violations(od, oc)}")
    for g, cols in groups.items():
        a, b = x_profile(d, c, cols), x_profile(od, oc, cols)
        rep.check(table, f"{g} columns: characters replaced per error cell (1 / 2 / 3+) within 8 points of the original",
                  all(abs(x - y) <= 0.08 for x, y in zip(a, b)), f"{a} vs original {b}")


HOSPITAL_GENERIC = {"street", "avenue", "road", "drive", "blvd", "medical", "center", "regional", "hospital", "memorial", "health"}


def natural_values(rep: "Report", base: str, table: str, c, cols) -> None:
    """Fictitious values read as names (10-02): no apostrophe other than a possessive 's or an
    O'; no word glued to itself ("Hawkhawk"); every word from the style's pool or the base's
    generic words. The first Beers builds had odd and offensive words from a 9.5k pool and cut
    apostrophes ("Bidder'i"); glued words were "corrected" as typos by the models."""
    from .beers_variants import FUNCTION, GENERIC
    from .hospital_variants import SYL, WORDS
    from .movies_variants import FIRST, TITLE_FUNCTION
    words_style = "words" in table
    syl = re.compile("(" + "|".join(sorted(SYL, key=len, reverse=True)) + ")+")
    alt = "(" + "|".join(sorted(WORDS, key=len, reverse=True)) + ")"
    pair = re.compile(alt + alt)
    from .beers_variants import TOWN_ENDINGS
    town = re.compile(alt + "(" + "|".join(TOWN_ENDINGS) + ")")
    generic = {"hospital": HOSPITAL_GENERIC, "beers": GENERIC | FUNCTION, "movies": TITLE_FUNCTION | set(FIRST)}[base]
    def ok(w: str) -> bool:
        w = unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode().lower()   # "Kölsch" is generic
        if w in generic or len(w) <= 2:
            return True
        if not words_style:
            return bool(syl.fullmatch(w))
        if w in WORDS:
            return True
        if base == "beers" and town.fullmatch(w):   # one-word towns: "Oakville"
            return True
        m = pair.fullmatch(w)
        return bool(m) and base == "movies" and m.group(1) != m.group(2)   # surnames: two distinct words
    for col in cols:
        vals = set(map(str, c[col]))
        toks = [t for v in vals for t in re.findall(r"[^\W\d_]+(?:'[^\W\d_]*)?|'[^\W\d_]+", v)]
        broken = sorted({t for t in toks if "'" in t and not re.fullmatch(r"[^\W\d_]+'s|O'[^\W\d_]+", t)})
        doubled = sorted({t for t in toks if any(t.lower() == w + w for w in WORDS)})
        odd = sorted({t for t in toks for w in [t.split("'")[0] if not t.startswith("O'") else t[2:]] if w and not ok(w)})
        bad = [f"{len(broken)} cut apostrophes {broken[:3]}" if broken else "", f"{len(doubled)} doubled {doubled[:3]}" if doubled else "",
               f"{len(odd)} words outside the pool {odd[:5]}" if odd else ""]
        rep.check(table, f"{col}: values read as names (apostrophes, doubled words, pool)", not any(bad), "; ".join(x for x in bad if x))


def xsub_violations(d, c) -> int:
    """Hospital errors are characters replaced by "x": cells where the dirty value is not that."""
    return sum(1 for col in c.columns for x, y in zip(d[col], c[col]) if x != y and
               (len(x) != len(y) or any(a != b and a != "x" for a, b in zip(x, y))))


class Report:
    def __init__(self):
        self.rows, self.failed = [], 0

    def check(self, table: str, name: str, ok: bool, detail="") -> None:
        self.rows.append({"table": table, "check": name, "ok": bool(ok), "detail": detail})
        self.failed += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f": {detail}" if detail != "" else ""))

    def note(self, table: str, name: str, value) -> None:
        self.rows.append({"table": table, "metric": name, "value": value})
        print(f"       {name}: {value}")


def surrogate(rep: Report, base: str, table: str, od, oc, identity) -> None:
    d, c = load(table)
    print(f"[{table}]")
    rep.check(table, "same shape as the original", d.shape == od.shape and list(c.columns) == list(oc.columns))
    if base == "movies":
        clean_people(rep, table, load(table)[1], oc)
    rep.check(table, "error cells where the original has them", ((d != c).values == (od != oc).values).all(),
              f"{int((d != c).sum().sum())} error cells")
    other = [x for x in oc.columns if x not in identity]
    rep.check(table, "non-identity cells identical to the original's (clean and dirty)",
              all(c[x].equals(oc[x]) and d[x].equals(od[x]) for x in other), f"{len(other)} columns")
    natural_values(rep, base, table, c, [x for x in identity if x != "Id"])
    for col in identity:
        if col in PEOPLE:   # a cell is a list of people: the mapping is per person
            pairs = {(a, b) for ov, sv in zip(oc[col], c[col]) for a, b in zip(_names(ov), _names(sv))}
            same_len = all(len(_names(ov)) == len(_names(sv)) for ov, sv in zip(oc[col], c[col]))
            real = {n for v in oc[PEOPLE].values.ravel() for n in _names(v)}
        else:
            pairs, same_len = set(zip(oc[col], c[col])), True
            real = set(oc[col])
        fwd, back = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
        rep.check(table, f"{col}: one fictitious value per real value, and back",
                  same_len and max(fwd.values()) == 1 and max(back.values()) == 1, f"{len(pairs)} values")
        fake = {b for _, b in pairs if b}
        rep.check(table, f"{col}: no fictitious value is a real one", not (fake & real), f"{len(fake & real)} collisions")
    if base == "movies":
        for col in ("Director", "Creator"):
            ko, ks = kinds(od, oc, col), kinds(d, c, col)
            dist = sum(abs(ko.get(k, 0) - ks.get(k, 0)) for k in set(ko) | set(ks))
            rep.check(table, f"{col}: error kinds as in the original (at most 4 cells apart)", dist <= 4, f"{ks} vs original {ko}")
        error_kinds(rep, base, table, d, c, od, oc)
        title_leaks(rep, table, d, c, od, oc)
    else:
        a, b = chars_changed(d, c, identity), chars_changed(od, oc, identity)
        rep.check(table, "identity errors are x-substitutions of the original's strength (within 0.35 characters)",
                  abs(a - b) <= 0.35, f"{a} characters changed per error, original {b}")
        hospital_strength(rep, table, d, c, od, oc, {"identity": identity})


def title_leaks(rep: Report, table: str, d, c, od, oc) -> None:
    """Movies surrogates: (1) no word of a real title (other than function words) in a
    fictitious title, its dirty variant or a Rotten Tomatoes slug; (2) title words come from the
    surrogate's own pool (WORDS, or syllables); (3) no title keeps its real title's shape (the
    sequence of function words, numbers and punctuation): a word-by-word rewrite did, and
    DeepSeek recognised films from it (10-02 pilot). Shapes may coincide by chance: the share
    must stay within 3 points of what random pairing gives."""
    from .hospital_variants import SYL, WORDS
    from .movies_variants import TITLE_FUNCTION
    fold = lambda w: unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode().lower()
    words = lambda vals: {fold(w) for v in vals for w in re.findall(r"[^\W\d_]{2,}", str(v))} - TITLE_FUNCTION - {"st", "nd", "rd", "th"}
    real = words(list(oc["Name"]) + list(od["Name"]) + [v for v, w in zip(od["Id"], oc["Id"]) if v != w])
    fake = words(list(c["Name"]) + list(d["Name"]) + [v for v, w in zip(d["Id"], c["Id"]) if v != w])
    rep.check(table, "no real title word in fictitious titles, title errors or slugs", not (real & fake),
              f"{len(real & fake)} shared, e.g. {sorted(real & fake)[:5]}")
    syl = re.compile("(" + "|".join(sorted(SYL, key=len, reverse=True)) + ")+")
    pool = (lambda w: w in WORDS) if "words" in table else (lambda w: bool(syl.fullmatch(w)))
    odd = sorted({w for w in words(list(c["Name"])) if not pool(w)})
    rep.check(table, "fictitious title words all from the surrogate's pool", not odd, f"{len(odd)} others, e.g. {odd[:5]}")
    shape = lambda t: re.sub(r"[^\W\d_]+", lambda m: m.group(0) if m.group(0).lower() in TITLE_FUNCTION else "X", str(t))
    so, sf = [shape(t) for t in oc["Name"]], [shape(t) for t in c["Name"]]
    same = sum(a == b for a, b in zip(so, sf)) / len(so)
    po, pf = collections.Counter(so), collections.Counter(sf)
    chance = sum(po[k] * pf[k] for k in po) / len(so) ** 2
    rep.check(table, "titles do not keep their real title's shape (no more than random pairing + 3 points)",
              same <= chance + 0.03, f"same shape {same:.1%}, by chance {chance:.1%}")
    # ...and look like the original's titles as a whole (the pilot of 10-02: repeated words and
    # over-long titles drew 24 edits of correct titles from DeepSeek)
    def rates(ts):
        ts = list(dict.fromkeys(ts))
        nw = [len(re.findall(r"[^\W\d_]+", t)) for t in ts]
        rep_w = [len(x) != len(set(x)) for x in ([w.lower() for w in re.findall(r"[^\W\d_]+", t)] for t in ts)]
        f = lambda pat: sum(bool(re.search(pat, t)) for t in ts) / len(ts)
        long = [t for t, k in zip(ts, nw) if k >= 4]
        plain = sum(1 for t in long if ":" not in t and not any(w.lower() in TITLE_FUNCTION for w in re.findall(r"[^\W\d_]+", t)))
        return {"words": sum(nw) / len(ts), "5+ words": sum(k >= 5 for k in nw) / len(ts), "repeated word": sum(rep_w) / len(ts),
                "4+ words, no function word or colon": plain / max(1, len(long)),
                "The ...": f(r"^The "), "lowercase word": f(r" (of|the|in|on|and|to|a|an|for|with|from|at)( |$)"),
                "colon": f(":"), "final number": f(r" \d+$"), "!": f(r"[!?]")}
    ro, rf = rates(oc["Name"]), rates(c["Name"])
    tol = {"words": 0.3, "5+ words": 0.05, "repeated word": 0.01, "4+ words, no function word or colon": 0.10}
    bad = {k: (round(rf[k], 3), round(ro[k], 3)) for k in ro if (rf[k] - ro[k] > tol[k] if k == "repeated word" else abs(rf[k] - ro[k]) > tol.get(k, 0.03))}
    rep.check(table, "fictitious titles like the original's: length, repeated words, The/lowercase/colon/number/! rates",
              not bad, f"off: {bad}" if bad else f"{ {k: round(v, 3) for k, v in rf.items()} }")


def clean_people(rep: Report, table: str, c, oc) -> None:
    """The clean table itself: no column repeats a person within a cell more often than the
    original does (the original's Creator has 68 such cells, a benchmark flaw the surrogates
    keep; the first fresh build took one IMDb row per role and wrote "Maggie Cheung" three
    times in 72 Actors cells, where the original has none)."""
    rep_cells = lambda t, col: [v for v in t[col] if len(_names(v)) != len({_fold(n) for n in _names(v)})]
    n = {col: (len(rep_cells(c, col)), len(rep_cells(oc, col))) for col in PEOPLE}
    rep.check(table, "clean people cells repeat a person no more often than the original's", all(a <= b for a, b in n.values()),
              f"{n} (table, original)")


def fresh(rep: Report, base: str, table: str, od, oc, identity, main_clean) -> None:
    d, c = load(table)
    print(f"[{table}]")
    rep.check(table, "same shape and columns as the original", d.shape == od.shape and list(c.columns) == list(oc.columns))
    rep.check(table, "same clean table as the main fresh table", c.equals(main_clean))
    if base == "hospital":
        n, no = (d != c).sum(), (od != oc).sum()
        rep.check(table, "the original's number of errors in every column", bool((n == no).all()), f"{int(n.sum())} error cells")
        a, b = chars_changed(d, c, identity), chars_changed(od, oc, identity)
        rep.check(table, "identity errors of the original's strength (within 0.2 characters)", abs(a - b) <= 0.2,
                  f"{a} characters changed per error, original {b}")
        hospital_strength(rep, table, d, c, od, oc, {"identity": identity, "other": [x for x in oc.columns if x not in identity]})
    else:
        _, _, rt = subset()
        ppl = (d[["Director", "Creator"]] != c[["Director", "Creator"]]).any(axis=1)
        rep.check(table, "people errors only in Rotten Tomatoes rows", not bool((ppl & ~rt).any()))
        rep.check(table, "Id and Year wrong in every Rotten Tomatoes row, nowhere else",
                  bool(((d["Id"] != c["Id"]) == rt).all() and ((d["Year"] != c["Year"]) == rt).all()))
        rep.check(table, "no film of the benchmark", not (set(c["Id"]) & set(load("movies_1")[1]["Id"])))
        clean_people(rep, table, c, oc)
        # Table-wide format errors follow the original's rules, not a random share of cells
        # (models "fix" the cells a random share leaves out: 269 RatingCount cells before 10-01).
        big = c["RatingCount"].map(lambda v: v.isdigit() and int(v) >= 1000)
        rule = d["RatingCount"] == c["RatingCount"].map(lambda v: f"{int(v):,}" if v.isdigit() else v)
        o_big = oc["RatingCount"].map(lambda v: v.isdigit() and int(v) >= 1000)
        rep.check(table, "RatingCount: thousands separators on every count >= 1000 and no other, as in the original",
                  bool(rule.all()) and bool(((od["RatingCount"] != oc["RatingCount"]) == o_big).all()),
                  f"{int((~rule).sum())} cells off the rule; {int(big.sum())} counts >= 1000 (original {int(o_big.sum())})")
        for col in ("Director", "Creator"):
            ko, kf = kinds(od, oc, col), kinds(d, c, col)
            no, nf = sum(ko.values()), sum(kf.values())
            # an error that cannot be made on the fresh value (reordering one name) leaves the cell clean
            rep.check(table, f"{col}: the original's error kinds (no kind more frequent than in the original by more than 2; at least 80% of its errors)",
                      all(kf.get(k, 0) <= ko.get(k, 0) + 2 for k in kf) and nf >= 0.8 * no, f"{kf} vs original {ko}")
        error_kinds(rep, base, table, d, c, od, oc, skip=("RatingCount",))   # RatingCount: the rule check above
        rep.note(table, "error cells per column", {x: int(v) for x, v in (d != c).sum().items() if v})
        rep.note(table, "original's error cells per column", {x: int(v) for x, v in (od != oc).sum().items() if v})


def beers(rep: Report) -> None:
    """Beers: every error is a format change (state glued onto the city with the state cell left
    empty; abv written as "<value>%"), so the checks are about the error forms and the renaming."""
    from .beers_variants import COLS, abv_error, city_error
    from .beers_variants import IDENTITY as B_ID
    od, oc = load("beers_orig")
    for kind in ("surrogatewords", "surrogate"):
        t = f"beers_{kind}"
        d, c = load(t)
        print(f"[{t}]")
        rep.check(t, "same shape as the original", d.shape == od.shape and list(c.columns) == list(oc.columns))
        rep.check(t, "error cells where the original has them", ((d != c).values == (od != oc).values).all())
        natural_values(rep, "beers", t, c, B_ID)
        other = [x for x in oc.columns if x not in B_ID and x != "state"]
        rep.check(t, "non-identity cells identical to the original's (clean and dirty)",
                  all(c[x].equals(oc[x]) and d[x].equals(od[x]) for x in other) and c["state"].equals(oc["state"])
                  and d["state"].equals(od["state"]), f"{other} and state")
        err = d["city"] != c["city"]
        rep.check(t, "city errors are the original's form: fictitious city + state, state cell empty",
                  all(city_error(c.at[i, "city"], oc.at[i, "state"]) == (d.at[i, "city"], d.at[i, "state"]) for i in err[err].index),
                  f"{int(err.sum())} city errors")
        for col in B_ID:
            pairs = set(zip(oc[col], c[col]))
            fwd, back = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
            rep.check(t, f"{col}: one fictitious value per real value, and back",
                      max(fwd.values()) == 1 and max(back.values()) == 1, f"{len(pairs)} values")
            kept = sum(a == b for a, b in pairs)
            other_real = {b for a, b in pairs if a != b} & set(oc[col])
            rep.check(t, f"{col}: no fictitious value is another entity's real value", not other_real,
                      f"{len(other_real)} collisions; {kept} values kept as they are (generic names such as \"IPA\")")
    d, c = load("beers_fresh")
    print("[beers_fresh]")
    rep.check("beers_fresh", "same shape and columns as the original", d.shape == od.shape and list(c.columns) == list(oc.columns))
    n, no = (d != c).sum(), (od != oc).sum()
    rep.check("beers_fresh", "the original's number of errors in every column", bool((n == no).all()),
              f"{ {k: int(v) for k, v in n.items() if v} } vs original { {k: int(v) for k, v in no.items() if v} }")
    err = d["city"] != c["city"]
    rep.check("beers_fresh", "city errors in the original's form",
              all(city_error(c.at[i, "city"], c.at[i, "state"]) == (d.at[i, "city"], d.at[i, "state"]) for i in err[err].index))
    err = d["abv"] != c["abv"]
    rep.check("beers_fresh", "abv errors in the original's form", all(abv_error(c.at[i, "abv"]) == d.at[i, "abv"] for i in err[err].index),
              f"{int(err.sum())} abv errors")
    from .beers_variants import LOCATION_FIXES
    locs = c.groupby("brewery-name")[["city", "state"]].nunique()
    rep.check("beers_fresh", "one city and state per brewery", bool((locs.max(axis=1) == 1).all()))
    wrong = [n for n, city, state in LOCATION_FIXES.values() if n in set(c["brewery-name"])
             and set(zip(c.loc[c["brewery-name"] == n, "city"], c.loc[c["brewery-name"] == n, "state"])) != {(city, state)}]
    rep.check("beers_fresh", "Wikidata locations checked by hand are the corrected ones (LOCATION_FIXES)", not wrong, f"{wrong}")
    error_kinds(rep, "beers", "beers_fresh", d, c, od, oc)
    for kind in ("surrogatewords", "surrogate"):
        error_kinds(rep, "beers", f"beers_{kind}", *load(f"beers_{kind}"), od, oc)
    rep.check("beers_fresh", "no beer of the benchmark", not (set(c["beer-name"].str.lower()) & set(load("beers")[1]["beer-name"].str.lower())),
              f"{len(set(c['beer-name'].str.lower()) & set(load('beers')[1]['beer-name'].str.lower()))} shared names")


def md5(path) -> str:
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def rebuild(rep: Report, seeds: list[int]) -> None:
    """Every surrogate and every seeded fresh table rebuilt twice elsewhere, files compared."""
    print("[rebuild under two PYTHONHASHSEED values]")
    jobs = [("hospital_variants", "surrogate", "hospital_surrogate"), ("hospital_variants", "surrogate-words", "hospital_surrogatewords"),
            ("movies_variants", "surrogate", "movies_surrogate"), ("movies_variants", "surrogate-words", "movies_surrogatewords"),
            ("hospital_variants", "fresh", "hospital_fresh"), ("movies_variants", "fresh", "movies_fresh")]
    with tempfile.TemporaryDirectory(dir=ROOT / "results") as tmp:
        for hs in ("1", "987"):
            for mod, cmd, name in jobs:
                for s in seeds:
                    if cmd == "fresh" and s == 0:
                        continue   # the main fresh tables need the downloaded sources; checked below instead
                    env = {**os.environ, "PYTHONHASHSEED": hs, "CORE_BUILD_DIR": f"{tmp}/{hs}"}
                    subprocess.run([sys.executable, "-m", f"src.{mod}", cmd, "--seed", str(s)], cwd=ROOT, env=env,
                                   check=True, stdout=subprocess.DEVNULL)
        for mod, cmd, name in jobs:
            for s in seeds:
                if cmd == "fresh" and s == 0:
                    continue
                t = seeded(name, s)
                same = all(md5(RAW / t / f) == md5(f"{tmp}/{hs}/{t}/{f}") for hs in ("1", "987") for f in ("clean.csv", "dirty.csv"))
                rep.check(t, "rebuilds byte for byte", same)
    if 0 in seeds:
        d, c = load("hospital_fresh")
        rep.check("hospital_fresh", "errors rebuild from the clean table", fresh_dirty(c, 0).equals(d))
        d, c = load("movies_fresh")
        _, _, rt = subset()
        new, _ = transfer_people(ErrorModel().dirty(c, list(rt), seed=0), c, 0)
        new, _ = transfer_names(new, c, 0)
        new, _ = transfer_genres(new, c)
        rep.check("movies_fresh", "errors rebuild from the clean table", new.equals(d))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--beers", action="store_true", help="also check the Beers tables (they have no seeds)")
    a = ap.parse_args()
    rep = Report()
    originals = {"hospital": (*load("hospital"), H_ID), "movies": (*subset()[:2], M_ID)}
    for base, (od, oc, identity) in originals.items():
        main_clean = load(f"{base}_fresh")[1]
        for s in a.seeds:
            fresh(rep, base, seeded(f"{base}_fresh", s), od, oc, identity, main_clean)
            for style in ("surrogatewords", "surrogate"):
                surrogate(rep, base, seeded(f"{base}_{style}", s), od, oc, identity)
        if len(a.seeds) > 1:   # the seeds must really differ
            print(f"[{base}: differences between seeds]")
            for kind in ("fresh", "surrogatewords", "surrogate"):
                tabs = [load(seeded(f"{base}_{kind}", s)) for s in a.seeds]
                # columns whose errors follow a fixed format rule are the same in every seed
                drawn = [x for x in tabs[0][1].columns if not (base == "movies" and x == "RatingCount")]
                for (s1, (d1, c1)), (s2, (d2, c2)) in zip(zip(a.seeds, tabs), list(zip(a.seeds, tabs))[1:]):
                    err = (d1[drawn] != c1[drawn]).values | (d2[drawn] != c2[drawn]).values
                    share = float(((d1[drawn].values != d2[drawn].values) & err).sum() / err.sum())
                    clean_diff = float((c1[identity].values != c2[identity].values).mean())
                    ok = share > 0.3 if (kind == "fresh" or base == "hospital") else clean_diff > 0.9
                    rep.check(f"{base}_{kind}", f"seed {s1} and seed {s2} are different draws", ok,
                              f"{share:.0%} of error cells differ; {clean_diff:.0%} of clean identity cells differ")
    if a.beers:
        beers(rep)
    if a.rebuild:
        rebuild(rep, a.seeds)
        if a.beers:   # Beers tables have no seeds: rebuild the two surrogates and compare
            with tempfile.TemporaryDirectory(dir=ROOT / "results") as tmp:
                for hs in ("1", "987"):
                    for cmd in ("surrogate", "surrogate-words"):
                        subprocess.run([sys.executable, "-m", "src.beers_variants", cmd], cwd=ROOT, check=True, stdout=subprocess.DEVNULL,
                                       env={**os.environ, "PYTHONHASHSEED": hs, "CORE_BUILD_DIR": f"{tmp}/{hs}"})
                for t in ("beers_surrogatewords", "beers_surrogate"):
                    same = all(md5(RAW / t / f) == md5(f"{tmp}/{hs}/{t}/{f}") for hs in ("1", "987") for f in ("clean.csv", "dirty.csv"))
                    rep.check(t, "rebuilds byte for byte", same)
    target = BUILD / "derived" / "validate_tables.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rep.rows, indent=1, ensure_ascii=False))
    print(f"\n{sum('check' in r for r in rep.rows)} checks, {rep.failed} failed")
    sys.exit(1 if rep.failed else 0)


if __name__ == "__main__":
    raise SystemExit("Use tools/core.py for public replay or explicit private validation; no implicit Movies reconstruction")
    main()
