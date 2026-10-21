"""Build the four CoRe conditions for Beers: original / fresh / words surrogate / pseudo surrogate.

Beers (Raha/Baran, scraped from CraftCans.com around 2017) has no errors in its names at all.
Every error is a format error whose correct value is already inside the dirty cell:
  ounces  "12.0 oz" -> "12"             (every row)
  ibu     "N/A" -> ""                    (every missing IBU)
  abv     "0.05%" -> "0.05"              (29% of rows; written as repr(percent / 100), hence
                                          "0.055999999999999994%" for 5.6%)
  city    "Boston MA" -> "Boston", state "" -> "MA"   (127 rows, mostly whole breweries)
So in CoRe, Beers is the negative control: knowing the beer or the brewery should not help,
and all four conditions should score alike if the surrogates do not make a table harder.

All four conditions share one schema, the columns Wikidata can fill (id, beer-name, style,
abv, brewery_id, brewery-name, city, state; ounces and ibu dropped), and 1000 rows.

- original ("beers_orig"; "beers" is the full benchmark): all 127 city/state-error rows plus
  873 random others, in benchmark order, errors untouched.
- fresh: 1000 US beers from Wikidata (CC0; mostly 2020s releases entered in 2025-2026) that
  are not in the benchmark, at most 25 per brewery; ids are synthetic. The same number of abv
  and city/state errors as the original subset, made the original's way.
- surrogate: the original subset with beer, brewery and city names rewritten word by word into
  real English words ("words") or meaningless syllables ("pseudo"). Generic beer words (Brewing,
  IPA, Stout...) are kept, and one real word always maps to one fictitious word, so a brewery
  keeps one name and "Portland Brewing" still sits in the city it names. City errors are
  regenerated from the fictitious city; abv errors are the original's.

Usage: .venv/bin/python -m src.beers_variants {original,fresh,surrogate,surrogate-words,all}
"""
import json
import random
import re
import sys

import pandas as pd

from .data import RAW, load
from .hospital_variants import SYL, WORDS, out_dir, save

COLS = ["id", "beer-name", "style", "abv", "brewery_id", "brewery-name", "city", "state"]
IDENTITY = ["beer-name", "brewery-name", "city"]
WIKIDATA = RAW / "_wikidata" / "beers_raw.csv"  # from beers.rq, 2026-09-29
BREWERIES = RAW / "_wikidata" / "breweries.csv"  # from breweries.rq, 2026-09-29
N_ROWS, SEED, PER_BREWERY = 1000, 0, 25


# --------------------------------------------------------------------------- errors
def abv_error(clean: str) -> str:
    """The original's abv error, reproduced exactly on all 693 cells: percent / 100 + "%"."""
    return repr(round(float(clean) * 100, 1) / 100) + "%"


def city_error(city: str, state: str) -> tuple[str, str]:
    """State glued onto the city, state cell left empty."""
    return f"{city} {state}", ""


# --------------------------------------------------------------------------- original
def subset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """The 1000-row evaluation set, in benchmark order."""
    dirty, clean = load("beers")
    city_err = dirty["city"] != clean["city"]
    others = [i for i in range(len(clean)) if not city_err[i]]
    rows = sorted(list(city_err[city_err].index) +
                  random.Random(SEED).sample(others, N_ROWS - int(city_err.sum())))
    return (dirty.loc[rows, COLS].reset_index(drop=True), clean.loc[rows, COLS].reset_index(drop=True))


def counts(d: pd.DataFrame, c: pd.DataFrame) -> dict:
    return {col: int((d[col] != c[col]).sum()) for col in COLS if (d[col] != c[col]).any()}


def build_original() -> dict:
    d, c = subset()
    save("beers_orig", d, c)
    info = {"source": "Raha/Baran beers (CraftCans.com)", "rows": len(c), "columns": COLS,
            "breweries": int(c["brewery_id"].nunique()), "error_cells": counts(d, c)}
    (out_dir("beers_orig") / "provenance.json").write_text(json.dumps(info, indent=1))
    return info


# --------------------------------------------------------------------------- fresh
def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def brewery_locations() -> pd.DataFrame:
    """One (city, state) per brewery. Wikidata links some breweries to the wrong place (Prison
    City Brewing of Auburn NY -> Auburn University, AL), so the city must be a human settlement
    in exactly one state; headquarters (P159) win over "located in" (P131)."""
    b = pd.read_csv(BREWERIES, dtype=str, keep_default_na=False)
    b = b[(b["settlement"] == "true") & (b["stateCode"] != "")]
    b = b.assign(rank=(b["via"] != "hq").astype(int)).sort_values(["m", "rank", "cityLabel"])
    one_state = b.groupby("m")["stateCode"].nunique() == 1
    b = b[b["m"].isin(one_state[one_state].index)].drop_duplicates("m")
    b = b.set_index("m")[["cityLabel", "stateCode"]]
    for qid, (_, city, state) in LOCATION_FIXES.items():
        b.loc[f"http://www.wikidata.org/entity/{qid}"] = [city, state]
    return b


# Breweries whose Wikidata headquarters is a same-named town in another state (or a nearby
# city). Found 10-01 when models rewrote these states on correct rows (GPT-6.1-Sol 105 cells);
# each checked against the brewery's own site or listings.
LOCATION_FIXES = {   # Wikidata item: (brewery, city, state), with the address found
    "Q140172031": ("Mortalis Brewing Company", "Avon", "NY"),       # 5660 Tec Dr, Avon NY (Wikidata: CT)
    "Q140219349": ("Evil Twin Brewing NYC", "Ridgewood", "NY"),     # 1616 George St, Ridgewood, Queens (NJ)
    "Q139981002": ("Magnify Brewing Company", "Fairfield", "NJ"),   # 1275 Bloomfield Ave, Fairfield NJ (CT)
    "Q140248807": ("450 North Brewing Company", "Columbus", "IN"),  # 8111 E 450 N, Columbus IN (OH)
    "Q140173116": ("J. Wakefield Brewing", "Miami", "FL"),          # 120 NW 24th St, Miami (Deerfield Beach)
    "Q140627840": ("CLAG Brewing Company", "Sandusky", "OH"),       # 218 Columbus Ave, Sandusky OH (MI)
    "Q140134433": ("Barrier Brewing Company", "Oceanside", "NY"),   # 3001 New St, Oceanside NY (CA)
    "Q140250632": ("RaR Brewing", "Cambridge", "MD"),               # 504 Poplar St, Cambridge MD (MA)
    "Q140219915": ("Troon Brewing", "Hopewell", "NJ"),              # Hopewell Rocky Hill Rd, Hopewell NJ (VA)
}


def wikidata_beers() -> pd.DataFrame:
    """US beers with ABV, style, brewery and brewery city/state, one row per beer."""
    w = pd.read_csv(WIKIDATA, dtype=str, keep_default_na=False).drop(columns=["city", "cityLabel", "stateCode"])
    w = w[w["styleLabel"] != ""]
    w = w[~w["bLabel"].str.fullmatch(r"Q\d+") & ~w["mLabel"].str.fullmatch(r"Q\d+")]
    w = w[w["abv"].astype(float).between(0.5, 20)]
    w = w.sort_values(["b", "styleLabel"]).drop_duplicates("b")
    w = w.join(brewery_locations(), on="m", how="inner")
    _, clean = load("beers")
    seen = set(zip(clean["beer-name"].map(norm_name), clean["brewery-name"].map(norm_name)))
    seen_beer = set(clean["beer-name"].map(norm_name))
    keep = [(norm_name(b), norm_name(m)) not in seen and norm_name(b) not in seen_beer
            for b, m in zip(w["bLabel"], w["mLabel"])]
    return w[keep].reset_index(drop=True)


def beer_label(name: str, brewery: str) -> str:
    """Drop Wikidata's disambiguation suffix, "Infinite Fractal (3 Sons)" -> "Infinite Fractal".
    Only when the parenthesis repeats the brewery's name: the benchmark has "(2015)" suffixes."""
    m = re.fullmatch(r"(.*\S)\s*\(([^()]*)\)", name)
    words = lambda s: set(re.findall(r"[a-z0-9]+", s.lower())) - {"brewing", "brewery", "co", "company", "beer"}
    return m.group(1) if m and words(m.group(2)) & words(brewery) else name


def style_case(s: str) -> str:
    """Wikidata's "sour beer" -> "Sour Beer", closer to the benchmark's "American IPA"."""
    return " ".join(t if t.isupper() else t[:1].upper() + t[1:] for t in s.split())


def build_fresh() -> dict:
    rng = random.Random(SEED + 3)
    od, oc = subset()
    target = counts(od, oc)
    w = wikidata_beers()
    pool = []
    for _, g in w.groupby("m"):
        idx = list(g.index)
        rng.shuffle(idx)
        pool.append(idx[:PER_BREWERY])
    flat = [i for grp in pool for i in grp]
    chosen = set(rng.sample(flat, N_ROWS))
    groups = [[i for i in grp if i in chosen] for grp in pool]
    groups = [g for g in groups if g]
    rng.shuffle(groups)  # benchmark rows are grouped by brewery, breweries in no clear order
    ids = sorted(rng.sample(range(1, 2700), N_ROWS), reverse=True)
    brewery_ids = rng.sample(range(0, 600), len(groups))
    rows, k = [], 0
    for bid, grp in zip(brewery_ids, groups):
        for i in grp:
            r = w.loc[i]
            rows.append({"id": str(ids[k]), "beer-name": beer_label(r["bLabel"], r["mLabel"]),
                         "style": style_case(r["styleLabel"]),
                         "abv": repr(round(float(r["abv"]) / 100, 3)), "brewery_id": str(bid),
                         "brewery-name": r["mLabel"], "city": r["cityLabel"], "state": r["stateCode"],
                         "_wikidata": r["b"].rsplit("/", 1)[-1]})
            k += 1
    c = pd.DataFrame(rows)
    qids = c.pop("_wikidata")
    # Errors: the same counts as the original subset, made the original's way. City errors hit
    # whole breweries (82% of the original's breweries are all-or-nothing), abv errors rows.
    d = c.copy()
    by_brewery = list(c.groupby("brewery_id").groups.values())
    rng.shuffle(by_brewery)
    left = target["city"]
    for grp in by_brewery:
        if left <= 0:
            break
        for i in list(grp)[:left]:
            d.at[i, "city"], d.at[i, "state"] = city_error(c.at[i, "city"], c.at[i, "state"])
        left -= len(grp)
    for i in rng.sample(range(len(c)), target["abv"]):
        d.at[i, "abv"] = abv_error(c.at[i, "abv"])
    save("beers_fresh", d, c)
    info = {"source": "Wikidata (CC0), query data/raw/_wikidata/beers.rq, run 2026-09-29",
            "rows": len(c), "breweries": len(groups), "columns": COLS,
            "error_cells": counts(d, c), "original_error_cells": target,
            "synthetic_columns": ["id", "brewery_id"],
            "location_fixes": "10-01: Wikidata city/state of 9 breweries corrected (LOCATION_FIXES)",
            "notes": "US beers with ABV, style and brewery city/state; not in the benchmark by beer "
                     "name; at most 25 per brewery; abv = Wikidata percent / 100",
            "wikidata_items": qids.tolist()}
    (out_dir("beers_fresh") / "provenance.json").write_text(json.dumps(info, indent=1))
    return {k: v for k, v in info.items() if k != "wikidata_items"}


# --------------------------------------------------------------------------- surrogate
# Words kept as they are. Function words (also in city names: "San", "Saint")...
FUNCTION = set("""
a an the of and & in on at for to with by from or is it my our your its no vol
san santa st saint mt los las el la de du
i ii iii iv v vi vii viii ix x
""".split())
# ...and the words every beer table uses, which name no particular beer or brewery. Place
# words (river, north, lake, golden...) are NOT here: "Great River Brewery" and the city
# "Golden" are proper names a model can recognise.
GENERIC = FUNCTION | set("""
brewing brewery breweries brewers brewer brewhouse brewpub beerworks brew brews company co
corp inc llc beer beers ale ales ipa apa dipa neipa ipl esb stout porter lager pilsner pils
pale amber red brown black blonde blond white wheat hefeweizen witbier weizen saison
sour gose kolsch bock doppelbock marzen oktoberfest dunkel helles lambic tripel dubbel quad
double imperial triple session hazy juicy barrel aged edition series project works craft
cellars taproom
""".split())
TOWN_ENDINGS = ["ville", "ton", "burg", "field", "wood", "dale", "port", "ford"]
# Words, digits and single other characters, in order.
_TOKEN = re.compile(r"[^\W\d_]+|\d+(?:st|nd|rd|th|ST|ND|RD|TH)?|.", re.S)


def recase(word: str, like: str) -> str:
    if like.isupper() and len(like) > 1:
        return word.upper()
    if like[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


class ValueNamer:
    """Fictitious beer, brewery and city names, value by value (v3, 10-02). Generic words
    ("Brewing Company", "IPA", "San") stay; every other word becomes a word of the small pool
    (WORDS, "words" style) or a syllable word ("pseudo"), distinct within the value, in the
    same case; numbers become other numbers of the same length; only a possessive "'s" and an
    "O'" keep their apostrophe. The same real value always gets the same fictitious one, and a
    brewery or beer named after a city of the table gets that city's fictitious name. The first
    builds rewrote word by word with a 9.5k-word pool: odd and offensive words ("Erection
    Statement"), apostrophes cut off ("Bidder'i", "Turnout' Doll'") and glued city words
    ("Juniperharvest"), which models "corrected" as typos."""

    def __init__(self, style: str, real: dict[str, set[str]], seed: int):
        self.style, self.rng, self.real = style, random.Random(seed), real
        self.numbers: dict[str, str] = {}
        self.done: dict[str, dict[str, str]] = {col: {} for col in IDENTITY}

    def word(self, like: str, used: set[str], town: bool = False) -> str:
        for tries in range(10_000):
            if self.style == "words" and town:
                w = self.rng.choice(WORDS) + self.rng.choice(TOWN_ENDINGS)
            elif self.style == "words":
                w = self.rng.choice(WORDS)
            else:
                w = "".join(self.rng.choice(SYL) for _ in range(max(2, min(4, round(len(like) / 3))) + tries // 50))
            if w not in used:
                used.add(w)
                return recase(w, like)
        raise RuntimeError("no word left")

    def number(self, digits: str) -> str:
        if len(digits) == 4 and 1900 <= int(digits) <= 2030:
            return digits   # a year ("Pils (2015)") names no beer; a random one ("(5171)") reads as an error
        if digits not in self.numbers:
            while True:
                n = str(self.rng.randint(10 ** (len(digits) - 1) if len(digits) > 1 else 1, 10 ** len(digits) - 1))
                if n != digits and n not in self.numbers.values():
                    break
            self.numbers[digits] = n
        return self.numbers[digits]

    def rewrite(self, value: str, keep: set[str], town: bool = False) -> str:
        toks, out, used, skip = _TOKEN.findall(value), [], set(), set()
        for k, t in enumerate(toks):
            if k in skip:
                continue
            prev, nxt = toks[k - 1] if k else "", toks[k + 1] if k + 1 < len(toks) else ""
            if t in ("'", "’"):
                after = toks[k + 2] if k + 2 < len(toks) else ""
                # a possessive ("Bell's") or an "O'" keeps it; a contraction loses its tail too
                # ("Don't" -> "Oak", not "Oakt"); between two words it becomes a space
                if (nxt.lower() == "s" and not after.isalpha()) or prev in ("O", "o"):
                    out.append(t)
                elif nxt.isalpha() and nxt.lower() in ("t", "d", "n", "ll", "re", "ve", "m", "i", "em", "er"):
                    skip.add(k + 1)
                elif prev.isalpha() and nxt.isalpha():
                    out.append(" ")
                continue
            if t[:1].isdigit():
                m = re.fullmatch(r"(\d+)(\D*)", t)
                n, suf = self.number(m[1]), m[2]
                if suf:
                    suf = "th" if n[-2:] in ("11", "12", "13") else {"1": "st", "2": "nd", "3": "rd"}.get(n[-1], "th")
                    suf = suf.upper() if m[2].isupper() else suf
                out.append(n + suf)
            elif t.isalpha() and len(t) > 1 and t.lower() not in keep:
                out.append(self.word(t, used, town))
            else:
                out.append(t)
        return re.sub(r"\s+", " ", "".join(out)).strip()

    def __call__(self, value: str, col: str, city_fakes: dict[str, str] | None = None) -> str:
        if value in self.done[col]:
            return self.done[col][value]
        taken = self.real[col] | set(self.done[col].values())
        for attempt in range(1000):
            if col == "city":
                # a one-word city stays one word, a town name in the words style ("Oakville"):
                # a second pool word ("Clear Shadow") read like the glued state of a city error,
                # and DeepSeek cut it 14 times (pilot, 10-02)
                one = len([w for w in re.findall(r"[^\W\d_]{2,}", value) if w.lower() not in FUNCTION]) == 1
                out = self.rewrite(value, FUNCTION, town=one)
            else:
                # a brewery or beer named after a city of the table gets that city's fictitious
                # name (unless that keeps colliding with another fictitious name)
                cities = [x for x in sorted(city_fakes or {}, key=len, reverse=True)
                          if attempt < 5 and re.search(rf"(?<!\w){re.escape(x)}(?!\w)", value)]
                if cities:
                    a, b = re.split(rf"(?<!\w){re.escape(cities[0])}(?!\w)", value, maxsplit=1)
                    out = re.sub(r"\s+", " ", " ".join(x for x in (self.rewrite(a, GENERIC), city_fakes[cities[0]],
                                                                   self.rewrite(b, GENERIC)) if x)).strip()
                    out = out.replace(" 's", "'s")
                else:
                    out = self.rewrite(value, GENERIC)
                if out == value:   # all generic ("Beer Works Brewery"): replace its longest word too
                    words = [w for w in re.findall(r"[^\W\d_]{2,}", value) if w.lower() not in FUNCTION]
                    if words:
                        out = self.rewrite(value, GENERIC - {max(words, key=len).lower()})
            if attempt >= 20 and col != "city":   # the pool has run out of one-word forms ("words" style): one more word
                out = self.word(value.split()[0] if value.split() else "Name", set(out.lower().split())) + " " + out
            if out not in taken:
                self.done[col][value] = out
                return out
        raise RuntimeError(f"no fictitious value for {value!r}")


def build_surrogate(style: str) -> dict:
    d, c = subset()
    real = {col: set(c[col]) for col in IDENTITY}
    name_it = ValueNamer(style, real, SEED + 50 + (1 if style == "words" else 2))
    sc = c.copy()
    sc["city"] = [name_it(v, "city") for v in c["city"]]
    cities = dict(name_it.done["city"])
    for col in ("brewery-name", "beer-name"):
        sc[col] = [name_it(v, col, cities) for v in c[col]]
    sd = d.copy()
    for col in ("beer-name", "brewery-name"):
        sd[col] = sc[col]  # no errors in names
    for i in range(len(c)):
        if d.at[i, "city"] != c.at[i, "city"]:
            sd.at[i, "city"], sd.at[i, "state"] = city_error(sc.at[i, "city"], c.at[i, "state"])
        else:
            sd.at[i, "city"] = sc.at[i, "city"]
    name = "beers_surrogatewords" if style == "words" else "beers_surrogate"
    save(name, sd, sc)
    same_cells = bool(((sd != sc) == (d != c)).all().all())
    unchanged = {col: int((sc[col] == c[col]).sum()) for col in IDENTITY}
    info = {"style": style, "rows": len(sc), "replaced_columns": IDENTITY,
            "names": "v3 (10-02): value by value, small pool, generic words kept (ValueNamer)",
            "values_left_unchanged": unchanged, "error_cells": counts(sd, sc), "same_error_cells_as_original": same_cells}
    (out_dir(name) / "provenance.json").write_text(json.dumps(info, indent=1))
    return info


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    builds = {"original": build_original, "fresh": build_fresh,
              "surrogate": lambda: build_surrogate("pseudo"),
              "surrogate-words": lambda: build_surrogate("words")}
    for name in (builds if cmd == "all" else [cmd]):
        print(name, json.dumps(builds[name](), indent=1, ensure_ascii=False))
