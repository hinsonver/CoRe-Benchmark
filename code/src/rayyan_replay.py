"""Version-bound offline Rayyan replay. Standard library only; never query PubMed or models."""
import argparse
import ast
from collections import Counter
import csv
import difflib
import hashlib
import json
from pathlib import Path
import random
import re
import unicodedata


def read_csv(path, columns=None):
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    cols = columns or rows[0]
    if any(len(r) != len(cols) for r in rows):
        raise ValueError("CSV column alignment: " + str(path))
    return cols, [dict(zip(cols, r)) for r in rows[1:]]


def functions(root):
    ns = {"json": json, "re": re, "difflib": difflib, "unicodedata": unicodedata}
    for name, wanted in [("probe_clean", {"parse", "norm", "metrics"}),
                         ("rayyan_audit", {"fold", "date_year", "pub_year", "differing_words", "judge"})]:
        tree = ast.parse((root / f"code/src/{name}.py").read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
        if len(nodes) != len(wanted):
            raise ValueError("Missing frozen pure functions")
        exec(compile(ast.Module(body=nodes, type_ignores=[]), name, "exec"), ns)
        if name == "rayyan_audit":
            ns["STRATA"] = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                                 and any(isinstance(t, ast.Name) and t.id == "STRATA" for t in n.targets))
    return ns


def date_conversion(value):
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2})", value)
    return f"{int(m[2])}/{int(m[3])}/{int(m[1]):02d}" if m else None


def score_table(cols, dirty, clean, output, skip, ns):
    totals = {g: Counter(errors=0, predicted=0, repaired=0, detected=0) for g in ("all", "identity", "other")}
    identity = {"article_title", "journal_title", "author_list"}
    date_rows = []
    for i, (d, g, v) in enumerate(zip(dirty, clean, output)):
        if i in skip:
            continue
        for c in cols:
            err, changed = d[c] != g[c], ns["norm"](v[c]) != ns["norm"](d[c])
            repaired = changed and err and ns["norm"](v[c]) == ns["norm"](g[c])
            count = {"errors": int(err), "predicted": int(changed), "detected": int(changed and err), "repaired": int(repaired)}
            for group in ("all", "identity" if c in identity else "other"):
                totals[group].update(count)
            if repaired and c == "article_jcreated_at":
                if v[c] != date_conversion(d[c]):
                    raise ValueError("Credited date does not reproduce saved conversion")
                date_rows.append(i)
    return {g: ns["metrics"](c) for g, c in totals.items()}, date_rows


def audit_replay(cols, dirty, clean, rows, ns, disposition):
    errors = {(i, c) for i, (d, g) in enumerate(zip(dirty, clean)) for c in cols if d[c] != g[c]}
    if len(errors) != 948:
        raise ValueError("Wrong audit input version")
    rng, expected, populations = random.Random(0), [], {}
    for s, chosen in ns["STRATA"].items():
        cells = [(i, c) for c in chosen for i in range(1000) if (i, c) in errors]
        populations[s] = len(cells)
        expected.extend((s, i, c) for i, c in rng.sample(cells, min(80, len(cells))))
    if expected != [(r["stratum"], r["row"], r["col"]) for r in rows]:
        raise ValueError("Saved stratified sample differs")
    grouped, flags, scalar = {}, {}, 0
    for r in rows:
        if r["dirty"] != dirty[r["row"]][r["col"]] or r["clean"] != clean[r["row"]][r["col"]]:
            raise ValueError("Audit sample value mismatch")
        if r.get("pmid") and r["stratum"] != "编码乱码":
            s = r["stratum"]
            rec = ({"pubdate": r["truth"]} if s == "日期" else {"pages": r["truth"]} if s == "页码" else
                   dict(zip(("issn", "essn"), r["truth"].split("/"))) if s == "ISSN" else
                   {"volume" if r["col"] == "article_jvolumn" else "issue": r["truth"]})
            value = ns["judge"](s, r["col"], r["dirty"], r["clean"], rec)
            if any(value[k] != r[k] for k in ("clean_ok", "dirty_ok")):
                raise ValueError("Saved scalar check mismatch")
            scalar += 1
    for s, n in populations.items():
        sampled = [r for r in rows if r["stratum"] == s]
        matched = [r for r in sampled if r.get("pmid")]
        flags[s] = [not r["clean_ok"] for r in matched]
        grouped[s] = {"population": n, "sampled": len(sampled), "matched": len(matched), "failed": sum(flags[s])}
    estimate = sum(populations[s] * sum(v) / len(v) for s, v in flags.items()) / 948
    rng = random.Random(0)
    bs = sorted(sum(populations[s] * sum(rng.choice(v) for _ in v) / len(v) for s, v in flags.items()) / 948 for _ in range(5000))
    interval = [bs[124], bs[4874]]
    if [estimate, interval] != [disposition["metric"]["estimate"], disposition["metric"]["interval_95"]]:
        raise ValueError("Frozen estimate or interval changed")
    dates = [(i, c) for i, c in errors if c == "article_jcreated_at"]
    if len(dates) != 722 or not all(date_conversion(dirty[i][c]) == clean[i][c] for i, c in dates):
        raise ValueError("Date conversion mismatch")
    annotations = disposition["case_annotations"]
    for a in annotations:
        r = next(r for r in rows if (r["row"], r["col"]) == (a["row_zero_based"], a["column"]))
        if not r["clean_ok"] or r["clean"] == r["truth"]:
            raise ValueError("Presence annotation mismatch")
    return {"estimate": estimate, "interval_95": interval, "sampled_cells": len(rows),
            "matched_cells": sum(v["matched"] for v in grouped.values()),
            "unique_matched_pmids": len({r["pmid"] for r in rows if r.get("pmid")}),
            "scalar_checks_replayed": scalar, "encoding_full_metadata_rejudged": False,
            "encoding_dirty_agreement": None, "strata": grouped,
            "presence_value_mismatch_annotations": annotations, "date_conversions": len(dates)}


def replay(root):
    root = Path(root)
    binding = json.loads((root / "data/manifests/RAYYAN_REPLAY.json").read_text())
    for name, digest in binding["files"].items():
        path = root / name
        if not path.is_file():
            raise FileNotFoundError("Required Rayyan dependency missing: " + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Rayyan dependency hash mismatch: " + name)
    ns = functions(root)
    cols, clean = read_csv(root / "data/final/rayyan/clean.csv")
    _, dirty = read_csv(root / "data/final/rayyan/dirty.csv", cols)
    tc = root / "artifacts/raw_outputs/e4/inputs/rayyan"
    _, tc_clean = read_csv(tc / "clean.csv", cols)
    _, tc_dirty = read_csv(tc / "dirty.csv", cols)
    work = root / "artifacts/raw_outputs/e4/tabclean/rayyan"
    _, output = read_csv(work / "final_cleaned.csv", cols)
    _, dev = read_csv(work / "dev_dirty.csv", cols)
    if not all(len(x) == 1000 for x in (clean, dirty, tc_clean, tc_dirty, output)):
        raise ValueError("Rayyan row count")
    if not all(dirty[i]["id"] == tc_dirty[i]["id"] == output[i]["id"] for i in range(1000)):
        raise ValueError("Rayyan row-ID alignment")
    sample = json.loads((root / "data/provenance/rayyan/dev-row-indices.json").read_text())
    indices = sample["indices_0based_in_sample_order"]
    if len(set(indices)) != len(indices) or len(indices) != 150:
        raise ValueError("Development indices")
    if len(indices) != 150 or [tc_dirty[i] for i in indices] != dev:
        raise ValueError("Development sample full values mismatch")
    totals, date_rows = score_table(cols, tc_dirty, tc_clean, output, set(indices), ns)
    expected = {"errors":808, "predicted":498, "detected":497, "repaired":461}
    if any(totals["all"][k] != v for k, v in expected.items()) or len(date_rows) != 434:
        raise ValueError("Saved TabClean score mismatch")
    if sum(d[c] != g[c] for d, g in zip(tc_dirty, tc_clean) for c in cols) != 960:
        raise ValueError("Wrong TabClean input version")
    audit = json.loads((root / "results/derived/rayyan_audit.json").read_text())
    disposition = json.loads((root / "data/provenance/rayyan/m06-criteria.json").read_text())
    checked = audit_replay(cols, dirty, clean, audit, ns, disposition)
    retrieval = json.loads((root / "data/provenance/rayyan/retrieval-status.json").read_text())
    return {"tabclean": {"scored_rows":850, "dev_rows":150, **totals},
            "credited_date_conversions":len(date_rows), "credited_date_fraction":len(date_rows)/461,
            "audit":checked, "retrieval":retrieval,
            "version_binding":"TabClean actual inputs; never audit-table substitution"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay(args.root)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text, end="")
