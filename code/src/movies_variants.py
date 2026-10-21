"""Build the four CoRe conditions for Movies: original / fresh / words surrogate / pseudo surrogate.

Movies (Raha movies_1) pairs IMDb with Rotten Tomatoes: the clean table is IMDb's, and 190
rows were swapped wholesale for their Rotten Tomatoes version (slug id, 3-year range, RT genre
taxonomy, "1 hr. 39 min.", "5.4/10,6/10" ratings...). Two table-wide format errors come on
top: thousands separators in RatingCount and "7" -> "7.0" in RatingValue.

All four conditions use one schema of the 10 columns IMDb's non-commercial datasets can fill
(Id, Name, Year, Director, Creator, Actors, Duration, RatingValue, RatingCount, Genre) and one
evaluation set of 1000 rows: the 190 Rotten Tomatoes rows plus 810 random others, so the
knowledge-heavy errors (ids, genres, credits) are not a handful of cells.

- original:  that 1000-row subset of the benchmark, errors untouched.
- fresh:     for each original film, another IMDb film of the same year and popularity that is
             not in the benchmark (known to models, never seen in this table), current IMDb
             data, dirtied with generators learned from the original's errors.
- surrogate: the subset with ids, titles and people replaced by fictitious ones, either real
             English words ("words") or meaningless syllables ("pseudo"); titles in generic shapes
             unrelated to the real title, with the original's title errors made by recipe; people
             errors copied name by name; other errors kept.

IMDb data (datasets.imdbws.com) is for personal and non-commercial use only: subject to applicable permission. This public package contains recipes, not movie data.

Usage: .venv/bin/python -m src.movies_variants {original,fresh,fresh-errors,surrogate,surrogate-words}
("fresh-errors" rebuilds only the fresh table's Director/Creator errors; see "people errors, v2".)
Add "--seed N" to fresh / surrogate / surrogate-words for another construction seed (table
data/raw/<name>_sN): the fresh table's generated errors are redrawn; a surrogate gets other
fictitious titles and people (its errors are copies of the original's, so they do not change).
"""
import collections
import gzip
import json
import math
import random
import re
import sys
import unicodedata

import pandas as pd

from .data import RAW, load
from .hospital_variants import SYL, WORDS, out_dir, save, seeded

COLS = ["Id", "Name", "Year", "Director", "Creator", "Actors", "Duration", "RatingValue",
        "RatingCount", "Genre"]
IDENTITY = ["Id", "Name", "Director", "Creator", "Actors"]
IMDB = RAW / "_imdb"
N_ROWS, SEED = 1000, 0


# --------------------------------------------------------------------------- evaluation subset
def subset() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """The 1000-row evaluation set (all RT rows + random others), in benchmark order."""
    dirty, clean = load("movies_1")
    rt = dirty["Id"] != clean["Id"]
    others = [i for i in range(len(clean)) if not rt[i]]
    rows = sorted(list(rt[rt].index) + random.Random(SEED).sample(others, N_ROWS - int(rt.sum())))
    d, c = dirty.loc[rows, COLS].reset_index(drop=True), clean.loc[rows, COLS].reset_index(drop=True)
    return d, c, rt[rows].reset_index(drop=True)


# --------------------------------------------------------------------------- error model
class ErrorModel:
    """Rotten-Tomatoes-row and format errors, with rates learned from the full original."""

    def __init__(self):
        d, c = load("movies_1")
        rt = d["Id"] != c["Id"]
        n_rt = int(rt.sum())
        cnt = lambda col: int(((d[col] != c[col]) & rt).sum())
        self.p = {col: cnt(col) / n_rt for col in ("Name", "Director", "Creator", "Duration", "RatingValue", "Genre")}
        ids = d["Id"][rt]
        self.p_prefix = sum(bool(re.match(r"\d+-", x)) for x in ids) / n_rt
        self.p_year = sum(bool(re.search(r"_\d{4}$", x)) for x in ids) / n_rt
        dur = [(a, b) for a, b in zip(c["Duration"][rt], d["Duration"][rt]) if a != b]
        self.p_dur_empty = sum(b == "" for _, b in dur) / len(dur)
        self.dur_diff = []
        for a, b in dur:
            mb, ma = re.fullmatch(r"(\d+) hr\. (\d+) min\.", b), re.fullmatch(r"(\d+) min", a)
            if mb and ma:
                self.dur_diff.append(int(mb[1]) * 60 + int(mb[2]) - int(ma[1]))
        rv = [(a, b) for a, b in zip(c["RatingValue"][rt], d["RatingValue"][rt]) if a != b]
        self.p_rv_empty = sum(b == "" for _, b in rv) / len(rv)
        # Table-wide format errors (outside RT rows).
        ints = [(a, b) for a, b in zip(c["RatingValue"][~rt], d["RatingValue"][~rt]) if re.fullmatch(r"\d+", a)]
        self.p_int_dot0 = sum(b == a + ".0" for a, b in ints) / len(ints)
        self.p_commas = float((d["RatingCount"] != c["RatingCount"]).mean())
        # IMDb genre -> Rotten Tomatoes genre, most frequent partner (same name if RT has it).
        rt_vocab = {g for x in d["Genre"][rt] for g in x.split(",") if g}
        pairs = collections.defaultdict(collections.Counter)
        for a, b in zip(c["Genre"][rt], d["Genre"][rt]):
            for g in a.split(","):
                for h in b.split(","):
                    pairs[g][h] += 1
        self.genre = {g: (g if g in rt_vocab else cnt.most_common(1)[0][0]) for g, cnt in pairs.items()}
        old = [(y, b) for y, b in zip(c["Year"][rt], d["Genre"][rt]) if int(y) < 1980]
        self.p_classics = sum("Classics" in b for _, b in old) / max(1, len(old))

    @staticmethod
    def slug(title: str) -> str:
        t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
        t = re.sub(r"^the\s+", "", t)
        t = re.sub(r"[^a-z0-9]+", "_", t.replace("'", "")).strip("_")
        return t

    def rt_id(self, name: str, year: str, rng) -> str:
        s = self.slug(name)
        u = rng.random()
        if u < self.p_prefix:
            return f"{rng.randint(1000000, 1099999)}-{s}"
        if u < self.p_prefix + self.p_year:
            return f"{s}_{year}"
        return s

    @staticmethod
    def rt_name(name: str) -> str:
        """RT capitalisation / '&' spelling of a title."""
        out = " ".join(w[:1].upper() + w[1:] for w in name.split(" "))
        if out == name:
            out = name.replace(" and ", " & ") if " and " in name else name.replace(" & ", " and ")
        return out

    @staticmethod
    def rt_people(value: str, rng) -> str:
        """RT credit variants: another order, a dropped name, or a duplicate spelling."""
        names = [n for n in value.split(",") if n]
        if len(names) > 1:
            return ",".join(names[:-1]) if rng.random() < 0.5 else ",".join(reversed(names))
        if names:
            n = names[0]
            plain = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
            return plain if plain != n else f"{n} (I),{n}"
        return value

    def rt_duration(self, value: str, rng) -> str:
        m = re.fullmatch(r"(\d+) min", value)
        if not m or rng.random() < self.p_dur_empty:
            return ""
        t = max(1, int(m[1]) + rng.choice(self.dur_diff or [0]))
        return f"{t // 60} hr. {t % 60} min."

    def rt_rating(self, value: str, rng) -> str:
        if rng.random() < self.p_rv_empty:
            return ""
        try:
            v = float(value)
        except ValueError:
            return value
        a = min(10, max(0, round(v + rng.gauss(-0.4, 0.7), 1)))
        b = min(10, max(0, round(v + rng.gauss(-0.4, 0.7))))
        return f"{a:g}/10,{b}/10"

    def rt_genre(self, value: str, year: str, rng) -> str:
        out = []
        for g in value.split(","):
            h = self.genre.get(g, g)
            if h and h not in out:
                out.append(h)
        if year.isdigit() and int(year) < 1980 and rng.random() < self.p_classics:
            out.insert(0, "Classics")
        return ",".join(out)

    def dirty(self, clean: pd.DataFrame, rt_rows, seed: int, keep: pd.DataFrame | None = None,
              only: list[str] | None = None) -> pd.DataFrame:
        """Apply RT-row errors to rows in rt_rows and table-wide format errors everywhere.
        With `keep`, cells outside `only` are copied from `keep` instead (used by surrogates to
        reuse the original's non-identity errors verbatim)."""
        rng = random.Random(seed)
        d = clean.copy()
        for i in range(len(clean)):
            r = clean.iloc[i]
            if rt_rows[i]:
                d.at[i, "Id"] = self.rt_id(r["Name"], r["Year"], rng)
                d.at[i, "Year"] = f"{int(r['Year']) - 1} {r['Year']} {int(r['Year']) + 1}" if r["Year"].isdigit() else r["Year"]
                if rng.random() < self.p["Name"]:
                    d.at[i, "Name"] = self.rt_name(r["Name"])
                for col in ("Director", "Creator"):
                    if rng.random() < self.p[col]:
                        d.at[i, col] = self.rt_people(r[col], rng)
                if rng.random() < self.p["Duration"]:
                    d.at[i, "Duration"] = self.rt_duration(r["Duration"], rng)
                if rng.random() < self.p["RatingValue"]:
                    d.at[i, "RatingValue"] = self.rt_rating(r["RatingValue"], rng)
                if rng.random() < self.p["Genre"]:
                    d.at[i, "Genre"] = self.rt_genre(r["Genre"], r["Year"], rng)
            else:
                if re.fullmatch(r"\d+", r["RatingValue"]) and rng.random() < self.p_int_dot0:
                    d.at[i, "RatingValue"] = r["RatingValue"] + ".0"
            # The original writes every count of 1000 or more with thousands separators (768 of
            # 768) and no other: a format rule, not a random error. Until 10-01 the fresh table
            # drew it with probability p_commas, leaving 269 uncommaed counts that models then
            # "fixed". The draw is kept so that every other generated error stays as it was.
            if r["RatingCount"].isdigit():
                rng.random()
                if int(r["RatingCount"]) >= 1000:
                    d.at[i, "RatingCount"] = f"{int(r['RatingCount']):,}"
        if keep is not None:
            for col in clean.columns:
                if col not in only:
                    d[col] = keep[col]
        return d


# --------------------------------------------------------------------------- IMDb
def read_tsv(name: str, usecols, filt=None, chunksize=2_000_000) -> pd.DataFrame:
    parts = []
    with gzip.open(IMDB / f"{name}.tsv.gz", "rt", encoding="utf-8") as f:
        for ch in pd.read_csv(f, sep="\t", usecols=usecols, dtype=str, quoting=3,
                              na_values="\\N", keep_default_na=False, chunksize=chunksize):
            parts.append(ch if filt is None else filt(ch))
    return pd.concat(parts, ignore_index=True)


def imdb_rows(tconsts: list[str]) -> pd.DataFrame:
    """Clean 10-column rows, in the benchmark's format, for the given IMDb ids."""
    want = set(tconsts)
    basics = read_tsv("title.basics", ["tconst", "primaryTitle", "startYear", "runtimeMinutes", "genres"],
                      lambda ch: ch[ch["tconst"].isin(want)]).set_index("tconst")
    ratings = read_tsv("title.ratings", ["tconst", "averageRating", "numVotes"],
                       lambda ch: ch[ch["tconst"].isin(want)]).set_index("tconst")
    crew = read_tsv("title.crew", ["tconst", "directors", "writers"],
                    lambda ch: ch[ch["tconst"].isin(want)]).set_index("tconst")
    princ = read_tsv("title.principals", ["tconst", "ordering", "nconst", "category"],
                     lambda ch: ch[ch["tconst"].isin(want) & ch["category"].isin(["actor", "actress"])])
    princ["ordering"] = princ["ordering"].astype(int)
    people = set(princ["nconst"])
    for col in ("directors", "writers"):
        for v in crew[col].dropna():
            people.update(v.split(","))
    names = read_tsv("name.basics", ["nconst", "primaryName"],
                     lambda ch: ch[ch["nconst"].isin(people)]).set_index("nconst")["primaryName"].to_dict()
    # Directors and writers: the first two distinct names. The original never lists more than two
    # (Director: 913 one, 87 two; Creator: 288 one, 680 two); until 10-02 the fresh table listed
    # every credited writer (up to 19).
    who = lambda v: ",".join(list(dict.fromkeys(names[n] for n in str(v).split(",") if n in names))[:2]) if isinstance(v, str) else ""
    # The first three distinct actors. title.principals has one row per role, so an actor with
    # three roles filled all three places ("Maggie Cheung,Maggie Cheung,Maggie Cheung", 72 films
    # before the 10-01 fix); the benchmark's Actors cells never repeat a name.
    actors = (princ.sort_values("ordering").groupby("tconst")["nconst"]
              .apply(lambda s: ",".join(list(dict.fromkeys(names[n] for n in s if n in names))[:3])).to_dict())
    rows = []
    for t in tconsts:
        b, r, cr = basics.loc[t], ratings.loc[t], crew.loc[t]
        rv = float(r["averageRating"])
        rows.append({
            "Id": t, "Name": b["primaryTitle"], "Year": str(b["startYear"]),
            "Director": who(cr["directors"]), "Creator": who(cr["writers"]),
            "Actors": actors.get(t, ""), "Duration": f"{b['runtimeMinutes']} min",
            "RatingValue": f"{rv:g}", "RatingCount": str(r["numVotes"]),
            "Genre": b["genres"] if isinstance(b["genres"], str) else "",
        })
    return pd.DataFrame(rows, columns=COLS)


def match_fresh(orig_ids: list[str], orig_years: list[str], exclude: set[str]) -> list[str]:
    """For each original film: an unused IMDb movie of the same year (widening to +/-2) with
    the closest current vote count, not in the benchmark, with runtime and genres present.
    Years come from the benchmark itself: some benchmark titles are TV movies or lack runtime
    or genres on IMDb, so they are not in the filtered candidate list."""
    basics = read_tsv("title.basics", ["tconst", "titleType", "startYear", "runtimeMinutes", "genres"],
                      lambda ch: ch[(ch["titleType"] == "movie") & ch["runtimeMinutes"].notna() & ch["genres"].notna()])
    ratings = read_tsv("title.ratings", ["tconst", "numVotes"]).set_index("tconst")["numVotes"].astype(int)
    basics = basics[basics["tconst"].isin(ratings.index)]
    basics["votes"] = basics["tconst"].map(ratings)
    by_year = {y: g.sort_values("votes") for y, g in basics[basics["votes"] >= 1000].groupby("startYear")}
    used, out = set(exclude), []
    for t, y in zip(orig_ids, orig_years):
        v = int(ratings.get(t, 1000))
        pick = None
        for dy in (0, 1, -1, 2, -2):
            g = by_year.get(str(int(y) + dy)) if y and str(y).isdigit() else None
            if g is None:
                continue
            g = g[~g["tconst"].isin(used)]
            if len(g):
                pick = g.iloc[(g["votes"].apply(lambda x: abs(math.log(x) - math.log(max(v, 1))))).argmin()]["tconst"]
                break
        if pick is None:
            raise RuntimeError(f"no fresh match for {t}")
        used.add(pick)
        out.append(pick)
    return out


# --------------------------------------------------------------------------- builds
def build_original() -> dict:
    d, c, rt = subset()
    save("movies", d, c)
    info = {"rows": len(c), "rt_rows": int(rt.sum()), "error_cells": int((d != c).sum().sum()),
            "note": "1000-row evaluation set of Raha movies_1: all 190 Rotten Tomatoes rows + 810 random others (seed 0), 10 IMDb-fillable columns"}
    (RAW / "movies" / "provenance.json").write_text(json.dumps(info, indent=1))
    return info


def build_fresh() -> dict:
    d, c, rt = subset()
    _, full = load("movies_1")
    fresh_ids = match_fresh(list(c["Id"]), list(c["Year"]), set(full["Id"]))
    clean = imdb_rows(fresh_ids)
    dirty = ErrorModel().dirty(clean, list(rt), seed=SEED)
    dirty, people = transfer_people(dirty, clean)   # v2: the original's people errors, row by row
    dirty, names = transfer_names(dirty, clean)     # v3: the original's title errors, recipe by recipe
    dirty, genres = transfer_genres(dirty, clean)   # v3: the original's genre errors, slot by slot
    save("movies_fresh", dirty, clean)
    info = {"rows": len(clean), "rt_rows": int(rt.sum()), "overlap_with_benchmark": len(set(fresh_ids) & set(full["Id"])),
            "error_cells": int((dirty != clean).sum().sum()), "original_error_cells": int((d != c).sum().sum()),
            "source": "IMDb non-commercial datasets (datasets.imdbws.com), downloaded 2026-09-28; personal/non-commercial use only",
            "people_errors": "v2 (09-30): Director/Creator errors copied from the original row by row", **people,
            "title_errors": "v3 (10-02): the original's 17 Name errors copied recipe by recipe", **names,
            "genre_errors": "v3 (10-02): the original's Genre errors copied slot by slot", **genres,
            "fixes": "10-01: Actors = first three distinct actors; RatingCount commas by the original's rule (>= 1000)"}
    (out_dir("movies_fresh") / "provenance.json").write_text(json.dumps(info, indent=1, ensure_ascii=False))
    return info


# --------------------------------------------------------------------------- people errors, v2
# The first build dirtied Director/Creator with rt_people(): reorder, drop the last name, or
# "Name (I),Name". The original's errors are something else: mostly people added from the
# Rotten Tomatoes credits (115 added names in 43 Director cells, 123 in 129 Creator cells),
# dropped names, and a few spelling variants of a credited name. A model that strips "(I)"
# repaired all 45 fresh Director errors, so "original - fresh" came out negative for it.
# v2 copies each original error onto the fresh film in the same row, name by name.
_SUFFIX = re.compile(r"\s*\(([IVX]+)\)$")


def _names(v: str) -> list[str]:
    return [n.strip() for n in str(v).split(",") if n.strip()]


def _fold(n: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", n) if not unicodedata.combining(ch)).lower()


def _tokens(n: str) -> list[str]:
    return [t.strip(".") for t in re.split(r"[\s\-]+", _fold(_SUFFIX.sub("", n))) if t.strip(".")]


def alias_kind(a: str, g: str) -> str | None:
    """How dirty name `a` is a variant of clean name `g`, or None if it is someone else."""
    import difflib
    if _SUFFIX.search(a) and _fold(_SUFFIX.sub("", a)) == _fold(g):
        return "suffix"
    ta, tg = _tokens(a), _tokens(g)
    if ta == tg:
        return "punct"
    if ta and set(ta) < set(tg) and ta[-1] == tg[-1]:
        return "fewer"
    if tg and set(tg) < set(ta) and tg[0] == ta[0]:
        return "more"
    if difflib.SequenceMatcher(None, _fold(a), _fold(g)).ratio() >= 0.8:
        return "spelling"
    return None


def people_template(dirty_v: str, clean_v: str, row_others: set[str]) -> list[tuple] | None:
    """The original error as a recipe over the clean cell's names: for each dirty name, in
    order, ("keep", j, accents_differ) / ("alias", j, kind, numeral) / ("other", in_row).
    None when the dirty cell is empty."""
    D, G = _names(dirty_v), _names(clean_v)
    if not D:
        return None
    fg, used, out = [_fold(g) for g in G], set(), []
    for a in D:
        j = next((k for k, f in enumerate(fg) if f == _fold(a) and k not in used), None)
        if j is not None:
            used.add(j)
            out.append(("keep", j, a != G[j]))
            continue
        hit = next(((k, alias_kind(a, g)) for k, g in enumerate(G) if alias_kind(a, g)), None)
        if hit:
            m = _SUFFIX.search(a)
            out.append(("alias", hit[0], hit[1], m[1] if m else "I"))
        else:
            out.append(("other", _fold(a) in row_others))
    return out


def make_alias(name: str, kind: str, numeral: str, rng) -> str:
    """A variant spelling of `name` of the same kind as the original's."""
    parts = name.split(" ")
    if kind == "suffix":
        return f"{name} ({numeral})"
    if kind == "punct" and ("-" in name or "." in name):
        return name.replace("-", " ") if "-" in name else name.replace(".", "")
    if kind in ("fewer", "more"):
        if len(parts) >= 3:                       # "Darren Lynn Bousman" -> "Darren Bousman"
            return " ".join(parts[:1] + parts[2:])
        if len(parts) == 2:                       # "John Whitesell" -> "John P. Whitesell"
            return f"{parts[0]} {rng.choice('ABCDEFGHJKLMNPRSTW')}. {parts[1]}"
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    if plain != name and plain:                   # "Jorge R. Gutiérrez" -> "Jorge R. Gutierrez"
        return plain
    w = max(range(len(parts)), key=lambda k: len(parts[k]))   # swap two letters: Turteltaub -> Turtletaub
    t = parts[w]
    spots = [k for k in range(1, len(t) - 2) if t[k] != t[k + 1] and t[k].isalpha() and t[k + 1].isalpha()]
    if spots:
        k = rng.choice(spots)
        parts[w] = t[:k] + t[k + 1] + t[k] + t[k + 2:]
        return " ".join(parts)
    return f"{name} ({numeral})"


def apply_template(tpl: list[tuple] | None, clean_v: str, n_orig: int, in_row: list[str],
                   related: list[str], elsewhere: list[str], rng) -> str:
    """Build the dirty cell for another film from an original error's recipe. `in_row` are the
    film's people in its other columns, `related` people credited on the film who are in none
    of its columns (what Rotten Tomatoes' extra credits are for the original), `elsewhere`
    people of other films as a last resort. Names the original's clean cell did not have
    (index >= n_orig) are kept at the end."""
    if tpl is None:
        return ""
    F = _names(clean_v)
    have = {_fold(n) for n in F}
    pools = {True: [n for n in in_row if _fold(n) not in have], False: [n for n in related if _fold(n) not in have]}
    out = []
    for step in tpl:
        if step[0] == "keep":
            if step[1] < len(F):
                n = F[step[1]]
                out.append(unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode() if step[2] else n)
        elif step[0] == "alias":
            if F:
                out.append(make_alias(F[min(step[1], len(F) - 1)], step[2], step[3], rng))
        else:
            pool = pools[step[1]] or pools[not step[1]]
            n = pool.pop(0) if pool else rng.choice([x for x in elsewhere if _fold(x) not in have])
            for p in pools.values():
                if n in p:
                    p.remove(n)
            have.add(_fold(n))
            out.append(n)
    out += F[n_orig:]
    return ",".join(out) if out else clean_v   # nothing left to write: the cell stays clean


def related_people(tconsts: list[str]) -> dict[str, list[str]]:
    """Everyone IMDb credits on each film (title.principals, any job, billing order). Cached."""
    path = IMDB / "fresh_related.json"
    if path.exists():
        return json.loads(path.read_text())
    want = set(tconsts)
    princ = read_tsv("title.principals", ["tconst", "ordering", "nconst"], lambda ch: ch[ch["tconst"].isin(want)])
    princ["ordering"] = princ["ordering"].astype(int)
    names = read_tsv("name.basics", ["nconst", "primaryName"],
                     lambda ch: ch[ch["nconst"].isin(set(princ["nconst"]))]).set_index("nconst")["primaryName"].to_dict()
    rel = {t: list(dict.fromkeys(names[n] for n in g.sort_values("ordering")["nconst"] if n in names))
           for t, g in princ.groupby("tconst")}
    path.write_text(json.dumps(rel, ensure_ascii=False))
    return rel


def transfer_people(dirty: pd.DataFrame, clean: pd.DataFrame, seed: int = SEED) -> tuple[pd.DataFrame, dict]:
    """Replace the fresh table's Director/Creator errors by copies of the original's, row by
    row (fresh row i stands for original row i). When the fresh cell has another number of names
    than the original's, or the error cannot be made on it (e.g. reordering a single name), the
    error goes to another Rotten Tomatoes row with as many names (v3, 10-02; until then it
    stayed on its row, or the cell stayed clean: 36 Director errors instead of 43). Every other
    cell of `dirty` is left as it is."""
    od, oc, rt = subset()
    moved_rng = random.Random(seed + 17)   # the moved errors draw from their own stream
    related = related_people(list(clean["Id"]))
    rng = random.Random(seed + 11)
    out = dirty.copy()
    all_directors = [n for v in clean["Director"] for n in _names(v)]
    stats = collections.Counter()
    def pools(j, col):
        row = [n for k in ("Director", "Creator", "Actors") if k != col for n in _names(clean.at[j, k])]
        in_cols = {_fold(n) for k in ("Director", "Creator", "Actors") for n in _names(clean.at[j, k])}
        return row, [n for n in related.get(clean.at[j, "Id"], []) if _fold(n) not in in_cols]
    for col in ("Director", "Creator"):
        out[col] = clean[col]
        not_possible = []
        for i in range(len(clean)):
            if od.at[i, col] == oc.at[i, col]:
                continue
            others = {_fold(n) for k in ("Director", "Creator", "Actors") if k != col for n in _names(oc.at[i, k])}
            tpl = people_template(od.at[i, col], oc.at[i, col], others)
            row = [n for k in ("Director", "Creator", "Actors") if k != col for n in _names(clean.at[i, k])]
            in_cols = {_fold(n) for k in ("Director", "Creator", "Actors") for n in _names(clean.at[i, k])}
            rel = [n for n in related.get(clean.at[i, "Id"], []) if _fold(n) not in in_cols]
            # The original's clean Creator repeats a name in 68 cells ("Mora Stephens,Mora
            # Stephens"): positions count distinct people, or "keep the second name" would keep
            # another person on a fresh cell and an added name would become a changed one.
            first: dict[str, int] = {}
            pos = {k: first.setdefault(_fold(g), len(first)) for k, g in enumerate(_names(oc.at[i, col]))}
            if tpl:
                tpl = [(st[0], pos[st[1]], *st[2:]) if st[0] in ("keep", "alias") else st for st in tpl]
            n_orig = len(first)
            stats[f"{col}: original errors"] += 1
            if tpl is not None and len(_names(clean.at[i, col])) != n_orig:
                # The recipe is over the original's names (keep the 2nd, drop the 1st...): on a
                # cell with another number of names it would turn into another kind of error
                # (v3, 10-02: 27 "missing names" against the original's 23). Moved below.
                not_possible.append((i, tpl, n_orig))
                continue
            new = apply_template(tpl, clean.at[i, col], n_orig, row, rel, all_directors, rng)
            if new != clean.at[i, col]:
                out.at[i, col] = new
                stats[f"{col}: copied"] += 1
            else:
                not_possible.append((i, tpl, n_orig))
        for i, tpl, n_orig in not_possible:
            # another Rotten Tomatoes row with as many names, no error of its own, not used yet
            free = [j for j in range(len(clean)) if rt[j] and od.at[j, col] == oc.at[j, col] and out.at[j, col] == clean.at[j, col]
                    and (tpl is None or len(_names(clean.at[j, col])) == n_orig)]
            moved_rng.shuffle(free)
            for j in free + [i]:   # last resort: its own row, names as they are
                row, rel = pools(j, col)
                new = apply_template(tpl, clean.at[j, col], n_orig, row, rel, all_directors, moved_rng)
                if new != clean.at[j, col] and out.at[j, col] == clean.at[j, col]:
                    out.at[j, col] = new
                    stats[f"{col}: copied" + (" to another RT row with as many names" if j != i else " on its own row (other number of names)")] += 1
                    break
            else:
                stats[f"{col}: left clean (no RT row can take it)"] += 1
    return out, dict(stats)


# --------------------------------------------------------------------------- title errors, v3
# The original's 17 Name errors are Rotten Tomatoes' title against IMDb's: capitalisation
# ("Pennies From Heaven"), "&" for "and", accents, punctuation, a subtitle added or dropped,
# a "3D" / "Vol." dropped, an article added or dropped. Until 10-02 the fresh table drew only
# the capitalisation kind (8 cells), and the surrogates, whose titles were random capitalised
# words, got ": The Movie" appended in all 17 cells (rt_name had nothing to change). v3 derives
# each original error's recipe (the edits that turn the clean title into the dirty one,
# checked by replaying them) and copies it: onto a fresh film whose title can take it, and,
# for the surrogates, through a word-by-word rewrite that keeps function words, numbers and
# punctuation, so every edit carries over as it is.
TITLE_LOWERABLE = {"This", "That", "Is", "It", "Its", "Who", "What", "Are", "Be", "Not"}
ACCENTS = {"deja": "déjà", "cafe": "café", "fiance": "fiancé", "naive": "naïve", "pokemon": "pokémon",
           "resume": "résumé", "amelie": "amélie", "rene": "rené"}


def _fold_ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def title_op(op: tuple, t: str, fresh: bool = False) -> str | None:
    """One edit on a title; None when it cannot be made. `fresh`: generalise the edits tied to
    a particular word (the token dropped, the word lowercased) to one this title has."""
    kind, arg = op
    out = None
    if kind == "case_up":
        out = " ".join(w[:1].upper() + w[1:] for w in t.split(" "))
    elif kind == "case_down":
        words = t.split(" ")
        targets = [arg] if not fresh else sorted(TITLE_LOWERABLE)
        for j in range(1, len(words)):
            if words[j] in targets:
                words[j] = words[j].lower()
                out = " ".join(words)
                break
    elif kind == "and_to_amp" and " and " in t:
        out = t.replace(" and ", " & ", 1)
    elif kind == "amp_to_and" and " & " in t:
        out = t.replace(" & ", " and ", 1)
    elif kind == "accent":
        if _fold_ascii(t) != t:
            out = _fold_ascii(t)
        else:
            words = t.split(" ")
            for j, w in enumerate(words):
                if w.lower() in ACCENTS:
                    a = ACCENTS[w.lower()]
                    words[j] = a[:1].upper() + a[1:] if w[:1].isupper() else a
                    out = " ".join(words)
                    break
    elif kind == "drop_char" and arg in t:
        out = re.sub(r"\s+", " ", t.replace(arg, "")).strip()
    elif kind == "append" and ":" not in t:
        out = t + arg
    elif kind == "drop_after_colon" and ":" in t:
        out = t.split(":")[0].rstrip()
    elif kind == "drop_token":
        if f" {arg}" in t:
            out = re.sub(r"\s+", " ", t.replace(f" {arg}", "", 1)).strip()
        elif fresh and re.search(r" \d+$", t):   # no "3D" / "Vol." among the fresh titles
            out = re.sub(r" \d+$", "", t)
    elif kind == "drop_article" and t.startswith("The "):
        out = t[4:]
    elif kind == "add_article" and not re.match(r"(The|A|An) ", t):
        out = "The " + t
    return out if out and out != t else None


def title_recipe(dirty: str, clean: str) -> list[tuple]:
    """The shortest list of edits (one or two) that turns the clean title into the dirty one."""
    words = clean.split(" ")
    ops = [("case_up", None), ("and_to_amp", None), ("amp_to_and", None), ("accent", None),
           ("drop_after_colon", None), ("drop_article", None), ("add_article", None)]
    ops += [("case_down", w) for w in words[1:] if w[:1].isupper()]
    ops += [("drop_char", ch) for ch in sorted(set(re.findall(r"[^\w\s]", clean)))]
    ops += [("drop_token", w) for w in words[1:]]
    if dirty.startswith(clean):
        ops.append(("append", dirty[len(clean):]))
    def run(recipe, t):
        for op in recipe:
            t = title_op(op, t)
            if t is None:
                return None
        return t
    for recipe in [[o] for o in ops] + [[a, b] for a in ops for b in ops if a != b]:
        if run(recipe, clean) == dirty:
            return recipe
    raise ValueError(f"no recipe for {clean!r} -> {dirty!r}")


def transfer_names(dirty: pd.DataFrame, clean: pd.DataFrame, seed: int = SEED) -> tuple[pd.DataFrame, dict]:
    """The fresh table's Name errors: each original error's recipe on a fresh film. Name errors
    sit in Rotten Tomatoes rows, so the film is the one in the same row when its title can take
    the edits, otherwise another RT row's that can (drawn with the seed), each film once."""
    od, oc, rt = subset()
    rng = random.Random(seed + 13)
    out = dirty.copy()
    out["Name"] = clean["Name"]
    used, stats = set(), collections.Counter()
    def apply(recipe, t):
        for op in recipe:
            t = title_op(op, t, fresh=True)
            if t is None:
                return None
        return t
    rt_rows = [i for i in range(len(clean)) if rt[i]]
    for i in range(len(oc)):
        if od.at[i, "Name"] == oc.at[i, "Name"]:
            continue
        recipe = title_recipe(od.at[i, "Name"], oc.at[i, "Name"])
        stats["Name: original errors"] += 1
        ok = [j for j in rt_rows if j not in used and apply(recipe, clean.at[j, "Name"])]
        if not ok and len(recipe) > 1:
            # Two edits no fresh title can take together ("Walking with Dinosaurs 3D" -> "Walking
            # With Dinosaurs": capitalise and drop "3D"; the fresh RT titles that end in a number
            # have no lowercase word): copy the last edit alone, recorded as a partial copy.
            recipe = recipe[-1:]
            ok = [j for j in rt_rows if j not in used and apply(recipe, clean.at[j, "Name"])]
            stats["Name: copied partly (one of two edits)"] += bool(ok)
        if not ok:
            stats["Name: no fresh title can take the edits"] += 1
            continue
        j = i if i in ok else rng.choice(ok)
        used.add(j)
        out.at[j, "Name"] = apply(recipe, clean.at[j, "Name"])
        stats["Name: copied" + (" (same row)" if j == i else " (other RT row)")] += 1
    return out, dict(stats)


def transfer_genres(dirty: pd.DataFrame, clean: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The fresh table's Genre errors, v3 (10-02): row by row from the original. A Rotten
    Tomatoes genre list has slots filled by the RT name of an IMDb genre ("Action" -> "Action &
    Adventure") and slots with other RT genres ("Classics", "Kids & Family"). The fresh row gets
    a Genre error when the original row has one, with the original's slots: the mapped slots
    filled with its own genres' RT names (in its order), the other slots copied as they are.
    Until 10-02 the generator drew each RT row's genres from the mapping alone: 134 errors
    instead of 180, 16 lists shorter than IMDb's instead of 40."""
    od, oc, rt = subset()
    em = ErrorModel()
    out = dirty.copy()
    out["Genre"] = clean["Genre"]
    stats = collections.Counter()
    for i in range(len(oc)):
        if od.at[i, "Genre"] == oc.at[i, "Genre"]:
            continue
        stats["Genre: original errors"] += 1
        mapped_o = {em.genre.get(g, g) for g in oc.at[i, "Genre"].split(",") if g}
        slots = [("map", None) if g in mapped_o else ("copy", g) for g in od.at[i, "Genre"].split(",") if g]
        mine = list(dict.fromkeys(em.genre.get(g, g) for g in clean.at[i, "Genre"].split(",") if g))
        new, k = [], 0
        for kind, g in slots:
            if kind == "copy":
                new.append(g)
            elif k < len(mine):
                new.append(mine[k])
                k += 1
        value = ",".join(dict.fromkeys(new))
        if value and value != clean.at[i, "Genre"]:
            out.at[i, "Genre"] = value
            stats["Genre: copied"] += 1
        else:
            stats["Genre: left clean (the slots give the IMDb list back)"] += 1
    return out, dict(stats)


# Surrogate titles, v3 (10-02). Titles are fictitious words in generic shapes ("The X", "X of
# the Y", "X: The Y Z", "X Y 2"), drawn at the original's rates and independent of the film, so
# no title carries its real title's shape. A word-by-word rewrite (tried first) kept function
# words, numbers and punctuation, and DeepSeek recognised films from that skeleton ("A Ordinal on
# Taxing Flush 4: The Joke Accession" -> "A Nightmare on Elm Street 4: The Dream Master", 29
# correct titles rewritten in the pilot). A row with a Name error gets a shape its recipe needs,
# and the recipe makes the dirty title.
# lowercase words between capitalised ones, as phrases ("of the", not a lone "the" between nouns)
SMALL_PHRASES = ["of"] * 30 + ["of the"] * 15 + ["in the"] * 10 + ["in"] * 4 + ["on the"] * 4 + ["on"] * 2 + \
                ["to"] * 5 + ["for"] * 3 + ["with"] * 3 + ["from"] * 2 + ["at the"] * 2
TITLE_FUNCTION = set("a an the of and in on at to for from with by or this that is it vs vol imax".split())
# the original's titles: words per title, function words included (212 one, 305 two, 211 three,
# 129 four, 79 five, 64 six+); 18.5% "The ...", 23.4% a lowercase function word (30% of the
# titles of 2+ words), 6.1% a colon, 2.9% a final number, 1.8% "!"
N_WORDS = ([1, 2, 3, 4, 5, 6], [212, 305, 211, 129, 79, 64])


def recipe_needs(recipe: list[tuple]) -> dict:
    """The shape a title needs for these edits to be possible."""
    need = {}
    for kind, arg in recipe:
        if kind == "case_up":
            need["small"] = True
        elif kind == "case_down":
            need["cap_word"] = arg
        elif kind == "and_to_amp":
            need["join"] = "and"
        elif kind == "amp_to_and":
            need["join"] = "&"
        elif kind == "drop_char":
            need["bang" if arg == "!" else "colon"] = True
        elif kind == "drop_after_colon":
            need["subtitle"] = True
        elif kind == "drop_token":
            need["token"] = arg
        elif kind == "drop_article":
            need["the"] = True
        elif kind in ("add_article", "append"):
            need["plain_start" if kind == "add_article" else "no_colon"] = True
    return need


def generic_title(rng: random.Random, words, need: dict | None = None, shorten: float = 0.0) -> str:
    """A fictitious title of the original's length (function words counted): `words(n)` gives n
    distinct capitalised fictitious words (a title never repeats one: DeepSeek dropped the
    repeat in "Copper Copper" as an error)."""
    need = need or {}
    total = size = rng.choices(*N_WORDS)[0]   # `size` decides the shape, `total` the length
    if shorten and total >= 3 and rng.random() < shorten:   # see build_surrogate: words style
        total -= 1
    lead = bool(need.get("the") or (not need.get("plain_start") and rng.random() < 0.185))
    if "join" in need:
        mid = [need["join"]]
    elif "cap_word" in need:
        mid = ["of", need["cap_word"]]
    elif need.get("small") or (total - lead >= 2 and not need.get("colon") and
                               rng.random() < {2: 0.05, 3: 0.35}.get(size - lead, 0.55)):
        # long titles mostly have function words (or a colon): 12% of the original's titles of
        # 4+ words have neither; DeepSeek cut long chains of nouns as errors (pilot, 10-02)
        mid = rng.choice(SMALL_PHRASES).split()
    else:
        mid = []
    tail = []
    if "token" in need:
        tail = ["Vol.", str(rng.randint(2, 4))] if need["token"] == "Vol." else [need["token"]]
    elif rng.random() < 0.029:
        tail = [str(rng.randint(2, 4))]
    two = bool(mid) or any(x in need for x in ("colon", "subtitle"))
    n = max(total - lead - len(mid) - len(tail), 2 if two else 1)
    w = words(n)
    if mid:
        w[1:1] = mid
    if lead:
        w.insert(0, "The")
    t = " ".join(w + tail)
    if need.get("subtitle"):
        sub: list[str] = []
        while len(sub) < 2:   # two more words, not repeating the title's
            x = words(2)[0]
            if x not in w and x not in sub:
                sub.append(x)
        t += ": The " + " ".join(sub)
    elif need.get("colon") or (not need.get("no_colon") and not mid and
                               rng.random() < (0.45 if size >= 4 else 0.05 if size == 3 else 0)):
        a = t.split(" ")
        # between two capitalised words, so the subtitle does not start with "of" or "the"
        cuts = [j for j in range(1, len(a)) if a[j - 1][:1].isupper() and a[j][:1].isupper()
                and a[j - 1].lower() not in TITLE_FUNCTION and a[j].lower().rstrip(".") not in TITLE_FUNCTION]
        if cuts:
            cut = cuts[len(cuts) // 2]
            t = " ".join(a[:cut]) + ": " + " ".join(a[cut:])
    if need.get("bang") or (not need.get("no_colon") and not t[-1].isdigit() and rng.random() < 0.018):
        t += "!"
    return t


def surrogate_title_error(recipe: list[tuple], clean: str, word, rng: random.Random) -> str:
    """The original's title edits on a fictitious title. Accents go on the first word (the
    original's "Deja Vu" -> "Déjà Vu"); an appended subtitle keeps its function words and
    "IMAX" / "3D", its other words become fictitious ones."""
    t = clean
    for kind, arg in recipe:
        if kind == "accent":   # on the first word that is not a function word
            words = t.split(" ")
            j = next(k for k, w in enumerate(words) if w.lower().strip(":!") not in TITLE_FUNCTION)
            acute = dict(zip("aeiouAEIOU", "áéíóúÁÉÍÓÚ"))
            out, n = [], 0
            for ch in words[j]:
                if n < 2 and ch in acute:
                    out.append(acute[ch])
                    n += 1
                else:
                    out.append(ch)
            words[j] = "".join(out)
            t = " ".join(words)
        elif kind == "append":
            text = re.sub(r"[^\W\d_]{2,}", lambda m: m.group(0) if m.group(0).lower() in TITLE_FUNCTION else word(), arg)
            t = t + text
        else:
            t = title_op((kind, arg), t)
        if t is None:
            raise ValueError(f"recipe {recipe} not possible on {clean!r}")
    return t


def build_fresh_seed(seed: int) -> dict:
    """The fresh table with another error seed: same films and clean table as movies_fresh, the
    generated errors (ids, titles, durations, ratings, genres, counts) redrawn, and the
    original's people errors copied again with this seed's spelling variants."""
    _, clean = load("movies_fresh")
    d, c, rt = subset()
    dirty = ErrorModel().dirty(clean, list(rt), seed=seed)
    dirty, people = transfer_people(dirty, clean, seed)
    dirty, names = transfer_names(dirty, clean, seed)
    dirty, genres = transfer_genres(dirty, clean)
    name = seeded("movies_fresh", seed)
    save(name, dirty, clean)
    info = {"seed": seed, "rows": len(clean), "error_cells": int((dirty != clean).sum().sum()),
            "note": "same clean table as movies_fresh; errors redrawn with this seed", **people, **names, **genres}
    (out_dir(name) / "provenance.json").write_text(json.dumps(info, indent=1, ensure_ascii=False))
    return info


def rebuild_fresh_errors() -> dict:
    """v2 of the fresh table's errors, from the existing fresh clean table."""
    dirty, clean = load("movies_fresh")
    new, stats = transfer_people(dirty, clean)
    save("movies_fresh", new, clean)
    info = json.loads((RAW / "movies_fresh" / "provenance.json").read_text())
    info.update({"error_cells": int((new != clean).sum().sum()),
                 "people_errors": "v2 (09-30): Director/Creator errors copied from the original row by row", **stats})
    (RAW / "movies_fresh" / "provenance.json").write_text(json.dumps(info, indent=1, ensure_ascii=False))
    return info


FIRST = ["anna", "ben", "clara", "david", "ella", "frank", "grace", "henry", "iris", "jack", "kate",
         "leo", "maya", "noah", "olive", "paul", "ruth", "sam", "tessa", "victor", "wendy", "hugo"]


def build_surrogate(style: str, seed: int = 0) -> dict:
    """seed 0 is the main surrogate; another seed draws other fictitious titles and people."""
    d, c, rt = subset()
    rng = random.Random(SEED + (1 if style == "words" else 2) + 100 * seed)
    word = (lambda n: " ".join(w.capitalize() for w in rng.sample(WORDS, n))) if style == "words" else \
           (lambda n: " ".join("".join(rng.choice(SYL) for _ in range(2)).capitalize() for _ in range(n)))
    # Words-style people get a compound English surname ("Anna Stonebrook"): first name + one
    # word gives only ~1.4k combinations, fewer than the ~5k people in 1000 films.
    # The two words of a surname are distinct: independent draws gave "Hawkhawk" (76 people).
    def two_words() -> str:
        a, b = rng.sample(WORDS, 2)
        return a.capitalize() + b
    person = (lambda: f"{rng.choice(FIRST).capitalize()} {two_words()}") if style == "words" else (lambda: word(2))
    people, titles, ids = {}, {}, {}
    real_people = {n for col in ("Director", "Creator", "Actors") for v in c[col] for n in v.split(",") if n}
    taken_people, taken_titles = set(real_people), set(c["Name"])
    def fresh_value(make, taken):
        v = make()
        while v in taken:
            v = make()
        taken.add(v)
        return v
    def fake_person(n):
        if n not in people:
            people[n] = fresh_value(person, taken_people)
        return people[n]
    # v3 (10-02): titles in generic shapes (generic_title), drawn from their own stream; the
    # first builds' whole-title draw is still made, unused, so the people and ids below come
    # out as before.
    trng = random.Random(SEED + 41 + (1 if style == "words" else 2) + 100 * seed)
    # words style: only WORDS that no real title uses ("Green", "Hope" are in real titles)
    in_titles = {_fold_ascii(w).lower() for t in list(c["Name"]) + list(d["Name"]) for w in re.findall(r"[^\W\d_]+", t)}
    title_pool = [w for w in WORDS if w not in in_titles]
    tword = (lambda: trng.choice(title_pool).capitalize()) if style == "words" else \
            (lambda: "".join(trng.choice(SYL) for _ in range(2)).capitalize())
    single_used: set[str] = set()
    def twords(n: int) -> list[str]:   # n distinct words
        if n == 1 and style == "words":
            # One-word titles are a fifth of the original's, but the pool has 46 words: once a
            # word is used as a whole title, the next one-word title takes two words. Compounds
            # ("Groveaspen", even "Canyonglen") read as a missing space: DeepSeek split 6 of them
            # in the pilots of 10-02.
            free = [x for x in title_pool if x not in single_used]
            if free:
                w = trng.choice(free)
                single_used.add(w)
                return [w.capitalize()]
            n = 2
        out: list[str] = []
        while len(out) < n:
            w = tword()
            if w not in out:
                out.append(w)
        return out
    recipes = {i: title_recipe(d.at[i, "Name"], c.at[i, "Name"]) for i in range(len(c)) if d.at[i, "Name"] != c.at[i, "Name"]}
    needs = {c.at[i, "Name"]: recipe_needs(r) for i, r in recipes.items()}
    fake_titles: dict[str, str] = {}
    used_ids: set[str] = set(c["Id"])
    taken_fake = set(c["Name"]) | set(d["Name"])
    sc = c.copy()
    for i in range(len(c)):
        t = c.at[i, "Name"]
        if t not in titles:
            titles[t] = fresh_value(lambda: word(rng.choice([2, 3])), taken_titles)
        if t not in fake_titles:
            # words style: the ~165 one-word titles the pool cannot give get two words; shortening
            # a third of the titles of 3+ words keeps the original's mean length
            fake_titles[t] = fresh_value(lambda: generic_title(trng, twords, needs.get(t), 0.35 if style == "words" else 0.0), taken_fake)
        sc.at[i, "Name"] = fake_titles[t]
        new_id = f"tt{rng.randint(1000000, 9999999)}"   # drawn on every row, as in the first builds
        if c.at[i, "Id"] not in ids:
            while new_id in used_ids:   # two films never share one (10-02: a seed drew the same id twice)
                new_id = f"tt{rng.randint(1000000, 9999999)}"
            ids[c.at[i, "Id"]] = new_id
            used_ids.add(new_id)
        sc.at[i, "Id"] = ids[c.at[i, "Id"]]
        for col in ("Director", "Creator", "Actors"):
            sc.at[i, col] = ",".join(fake_person(n) for n in c.at[i, col].split(",") if n)
    dirty_names = {i: surrogate_title_error(r, sc.at[i, "Name"], tword, trng) for i, r in recipes.items()}
    em = ErrorModel()
    # Identity errors are regenerated from the fictitious values in the same cells (same kind);
    # every other error is the original's, byte for byte.
    gen = random.Random(SEED + 7 + 100 * seed)
    sd = d.copy()
    for i in range(len(c)):
        for col in IDENTITY:
            if d.at[i, col] == c.at[i, col]:
                sd.at[i, col] = sc.at[i, col]
            elif col == "Id":   # RT slug of the RT title, in the original slug's form (prefix, year)
                orig = d.at[i, col]
                sl = em.slug(dirty_names.get(i, sc.at[i, "Name"]))
                sd.at[i, col] = (orig.split("-")[0] + "-" + sl) if re.match(r"\d+-", orig) else \
                                (f"{sl}_{c.at[i, 'Year']}" if re.search(r"_\d{4}$", orig) else sl)
            elif col == "Name":   # the original's recipe on the fictitious title
                sd.at[i, col] = dirty_names[i]
            elif not d.at[i, col]:
                sd.at[i, col] = ""
            else:
                # v2 (09-30): the original error, name by name (the first build drew a generic
                # error with rt_people: reorder, drop the last name, or "Name (I),Name"). Kept
                # names become their fictitious counterparts, spelling variants are made on the
                # fictitious name, and people the original adds are mapped like everyone else,
                # so one added person is the same fictitious person wherever they appear.
                others = {_fold(n) for k in ("Director", "Creator", "Actors") if k != col for n in _names(c.at[i, k])}
                tpl, fake = people_template(d.at[i, col], c.at[i, col], others), _names(sc.at[i, col])
                names = []
                for step, real in zip(tpl, _names(d.at[i, col])):
                    if step[0] == "keep":
                        names.append(make_alias(fake[step[1]], "spelling", "I", gen) if step[2] else fake[step[1]])
                    elif step[0] == "alias":
                        names.append(make_alias(fake[step[1]], step[2], step[3], gen))
                    else:
                        names.append(fake_person(real))
                out = ",".join(names)
                sd.at[i, col] = out if out != sc.at[i, col] else sc.at[i, col] + " (I)"
    name = seeded("movies_surrogatewords" if style == "words" else "movies_surrogate", seed)
    save(name, sd, sc)
    info = {"style": style, "seed": seed, "rows": len(sc), "replaced_columns": IDENTITY,
            "error_cells": int((sd != sc).sum().sum()), "original_error_cells": int((d != c).sum().sum()),
            "same_error_cells_as_original": bool(((sd != sc) == (d != c)).all().all()),
            "people_errors": "v2 (09-30): Director/Creator errors copied from the original name by name",
            "titles": "v3 (10-02): fictitious titles in generic shapes at the original's rates; the original's title errors by recipe"}
    (out_dir(name) / "provenance.json").write_text(json.dumps(info, indent=1))
    return info


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "original"
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 0
    build = {"original": build_original, "fresh": (lambda: build_fresh_seed(seed)) if seed else build_fresh,
             "fresh-errors": rebuild_fresh_errors,
             "surrogate": lambda: build_surrogate("pseudo", seed),
             "surrogate-words": lambda: build_surrogate("words", seed)}[cmd]
    print(json.dumps(build(), indent=1, ensure_ascii=False))
