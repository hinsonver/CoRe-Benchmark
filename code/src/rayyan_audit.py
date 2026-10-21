"""Audit Rayyan's ground truth against PubMed.

A stratified random sample of Rayyan's error cells (dirty != clean) is checked against the
article's PubMed record (NCBI E-utilities, public). The record is accepted only when its title
matches the Rayyan title (similarity >= 0.9). For each cell we ask whether the benchmark's
clean value, and the dirty value, agree with the real one:

  pagination, ISSN       equal to PubMed's pages / ISSN or eISSN
  created-at date        its year equals the PubMed publication year (the field's exact meaning
                         is undocumented, so only the year is compared)
  encoding (title,       the words that differ between dirty and clean, compared with the
   journal, authors)     PubMed spelling (accents kept)
  volume/issue "-1"      whether PubMed has a real volume/issue

Usage: .venv/bin/python -m src.rayyan_audit [--per-stratum 30]
Output: results/rayyan_audit.json (every checked cell) and a summary on stdout.
"""
import argparse
import collections
import difflib
import json
import random
import re
import time
import unicodedata
import urllib.parse
import urllib.request

from .data import ROOT, load

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
OUT = ROOT / "results" / "rayyan_audit.json"
STRATA = {"日期": ["article_jcreated_at"], "编码乱码": ["article_title", "journal_title", "author_list"],
          "缺失写成-1": ["article_jvolumn", "article_jissue"], "页码": ["article_pagination"],
          "ISSN": ["journal_issn"]}


def get(url: str) -> dict:
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 * (i + 1))
    raise RuntimeError(url)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").casefold()
    return re.sub(r"[\W_]+", " ", s).strip()


def pubmed(title: str) -> dict | None:
    """The PubMed record whose title matches, or None."""
    words = [w for w in re.findall(r"[A-Za-z]+", title) if len(w) > 3][:8]
    if len(words) < 2:
        return None
    term = urllib.parse.quote(" AND ".join(f"{w}[ti]" for w in words))
    ids = get(f"{EUTILS}esearch.fcgi?db=pubmed&retmode=json&retmax=5&term={term}")["esearchresult"]["idlist"]
    time.sleep(0.35)
    if not ids:
        return None
    res = get(f"{EUTILS}esummary.fcgi?db=pubmed&retmode=json&id={','.join(ids)}")["result"]
    time.sleep(0.35)
    best = max((res[i] for i in ids), key=lambda r: difflib.SequenceMatcher(None, fold(r.get("title", "")), fold(title)).ratio())
    sim = difflib.SequenceMatcher(None, fold(best.get("title", "")), fold(title)).ratio()
    return best if sim >= 0.9 else None


def pub_year(rec: dict) -> str:
    m = re.match(r"(\d{4})", rec.get("pubdate", ""))
    return m.group(1) if m else ""


def date_year(v: str) -> str:
    m = re.fullmatch(r"\d{1,2}/\d{1,2}/(\d{2})", v.strip())
    if not m:
        return ""
    yy = int(m.group(1))
    return str(2000 + yy if yy <= 26 else 1900 + yy)


def differing_words(dirty: str, clean: str) -> list[str]:
    """Clean-side words that differ from the dirty side (where the encoding damage is)."""
    d, c = re.findall(r"[^\s,\"{}]+", dirty), re.findall(r"[^\s,\"{}]+", clean)
    return [w for w in c if w not in d]


def judge(stratum: str, col: str, dv: str, cv: str, rec: dict) -> dict:
    if stratum == "页码":
        truth = rec.get("pages", "")
        return {"truth": truth, "clean_ok": cv == truth, "dirty_ok": dv == truth}
    if stratum == "ISSN":
        truth = {rec.get("issn", ""), rec.get("essn", "")} - {""}
        return {"truth": "/".join(sorted(truth)), "clean_ok": cv in truth, "dirty_ok": dv in truth}
    if stratum == "日期":
        y = pub_year(rec)
        return {"truth": y, "clean_ok": date_year(cv) == y, "dirty_ok": date_year(dv) == y}
    if stratum == "缺失写成-1":
        truth = rec.get("volume" if col == "article_jvolumn" else "issue", "")
        return {"truth": truth, "clean_ok": (cv == "-1") == (truth == ""), "dirty_ok": (dv == "") == (truth == "")}
    # encoding: are the damaged words spelled as in PubMed?
    if col == "author_list":
        real = " ".join(a["name"] for a in rec.get("authors", []))
    elif col == "journal_title":
        real = rec.get("fulljournalname", "") + " " + rec.get("source", "")
    else:
        real = rec.get("title", "")
    real_words = set(unicodedata.normalize("NFC", real).casefold().split())
    words = [w.strip(".;:()[]").casefold() for w in differing_words(dv, cv)]
    words = [w for w in words if w]
    return {"truth": real[:120], "words": words,
            "clean_ok": bool(words) and all(w in real_words for w in words), "dirty_ok": False}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-stratum", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    dirty, clean = load("rayyan")
    rng = random.Random(a.seed)
    rows = []
    for stratum, cols in STRATA.items():
        cells = [(i, c) for c in cols for i in range(len(clean)) if dirty.at[i, c] != clean.at[i, c]]
        for i, c in rng.sample(cells, min(a.per_stratum, len(cells))):
            rows.append({"stratum": stratum, "row": i, "col": c, "dirty": dirty.at[i, c], "clean": clean.at[i, c],
                         "title": clean.at[i, "article_title"] or dirty.at[i, "article_title"],
                         "population": len(cells)})
    cache = {}
    for r in rows:
        t = r["title"]
        if t not in cache:
            try:
                cache[t] = pubmed(t)
            except RuntimeError:
                cache[t] = None
        rec = cache[t]
        r["pmid"] = rec.get("uid") if rec else None
        if rec:
            r.update(judge(r["stratum"], r["col"], r["dirty"], r["clean"], rec))
        print(r["stratum"], r["pmid"], r.get("clean_ok"), flush=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    summary(rows)


def summary(rows: list[dict]) -> None:
    by = collections.defaultdict(list)
    for r in rows:
        by[r["stratum"]].append(r)
    print(f"\n{'类型':8s} {'抽样':>4s} {'找到':>4s} {'标准答案正确':>8s} {'脏值正确':>6s}  总体规模")
    for s, rs in by.items():
        found = [r for r in rs if r.get("pmid")]
        ok = sum(r["clean_ok"] for r in found)
        dok = sum(r["dirty_ok"] for r in found)
        print(f"{s:8s} {len(rs):4d} {len(found):4d} {ok:4d}/{len(found):<4d} {dok:4d}/{len(found):<4d}  {rs[0]['population']}")


if __name__ == "__main__":
    main()
