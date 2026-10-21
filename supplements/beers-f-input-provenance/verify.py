"""Portable, standard-library-only replay of three explicitly bound Beers F archives."""
import ast
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archived_functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"parse", "norm", "metrics"}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == 3, "archived parser/normalization/metrics missing"
    ns = {"json": json, "re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    constants = {t.id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name) and t.id in {"PROMPT", "SYSTEM"}}
    return ns, constants


def read_table(folder):
    pairs = []
    for name in ("dirty", "clean"):
        with (folder / (name + ".csv")).open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        pairs.append(rows)
    assert pairs[0][0] == pairs[1][0], "column alignment"
    cols = pairs[0][0]
    dirty, clean = pairs[0][1:], pairs[1][1:]
    assert len(dirty) == len(clean) == 1000, "row count"
    assert all(len(r) == len(cols) for r in dirty + clean), "cell alignment"
    return cols, dirty, clean


def effective_predictions(cols, dirty, chunk, funcs):
    pred = {}
    for item in funcs["parse"](chunk["output"]):
        try:
            r = int(item["row"]) - 1
        except (TypeError, ValueError):
            continue
        col, value = str(item["column"]), str(item["value"]).strip()
        if 0 <= r < len(chunk["rows"]) and col in cols:
            i = chunk["rows"][r]
            if funcs["norm"](value) != funcs["norm"](dirty[i][cols.index(col)]):
                pred[i, col] = value
    return pred


def score_reply(cols, dirty, clean, chunk, funcs):
    pred = effective_predictions(cols, dirty, chunk, funcs)
    errors = {(i, c) for i in chunk["rows"] for j, c in enumerate(cols) if dirty[i][j] != clean[i][j]}
    identity = {"beer-name", "brewery-name", "city"}
    out = {}
    for group, keep in [("all", set(cols)), ("identity", identity), ("other", set(cols) - identity)]:
        es = {x for x in errors if x[1] in keep}
        ps = {x: v for x, v in pred.items() if x[1] in keep}
        out[group] = {"errors": len(es), "predicted": len(ps),
                      "detected": sum(x in es for x in ps),
                      "repaired": sum(x in es and funcs["norm"](v) ==
                                      funcs["norm"](clean[x[0]][cols.index(x[1])]) for x, v in ps.items())}
    return out


def prompt_key(model, cols, dirty, chunk, constants, budget):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["_row"] + cols)
    writer.writerows([[r + 1] + dirty[i] for r, i in enumerate(chunk["rows"])])
    prompt = constants["PROMPT"].format(block=stream.getvalue().rstrip("\n"))
    return hashlib.sha256(json.dumps([model, constants["SYSTEM"], prompt, budget]).encode()).hexdigest()


def verify_bundle(root):
    root = Path(root)
    manifest = json.loads((root / "MANIFEST.json").read_text())
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    assert actual == set(manifest) | {"MANIFEST.json"}, "unexpected or missing bundle files"
    for name, digest in manifest.items():
        assert sha(root / name) == digest, "checksum mismatch: " + name
    mapping = json.loads((root / "run-input-map.json").read_text())
    assert mapping["scope"] == "three archived Beers F runs only", "scope"
    assert len(mapping["runs"]) == 3, "run mapping count"
    funcs, constants = archived_functions(root / "source/probe_clean.py")
    historical = read_table(root / "inputs/historical")
    final = read_table(root / "inputs/final")
    cols, dirty, clean = historical
    assert cols == final[0], "input schemas"
    old_errors = {(i, c) for i in range(1000) for j, c in enumerate(cols) if dirty[i][j] != clean[i][j]}
    new_errors = {(i, c) for i in range(1000) for j, c in enumerate(cols) if final[1][i][j] != final[2][i][j]}
    assert old_errors == new_errors and len(old_errors) == 565, "error mask changed"
    witnesses = {r["key"]: r for r in map(json.loads, (root / "response-witnesses.jsonl").read_text().splitlines())}
    historical_equal = summary_equal = witness_equal = 0
    mismatch = {}
    for item in mapping["runs"]:
        assert item["scored_input"] == "inputs/historical", "historical input binding required"
        assert sha(root / item["run"]) == item["run_sha256"], "run binding"
        for name in ("dirty", "clean"):
            assert sha(root / item["scored_input"] / (name + ".csv")) == item["input_sha256"][name], "input binding"
        run = json.loads((root / item["run"]).read_text())
        assert run["summary"]["model"] == item["model"], "model binding"
        assert len(run["chunks"]) == 50, "chunk count"
        assert sorted(i for ch in run["chunks"] for i in ch["rows"]) == list(range(1000)), "row coverage"
        totals = {g: Counter() for g in ("all", "identity", "other")}
        bad = []
        for index, chunk in enumerate(run["chunks"]):
            old_count = score_reply(*historical, chunk, funcs)
            final_count = score_reply(*final, chunk, funcs)
            assert old_count == chunk["counts"], f"historical score: {item['model']} chunk {index}"
            assert len(funcs["parse"](chunk["output"])) == chunk["n_pred"], "parsed item count"
            historical_equal += 1
            if final_count != chunk["counts"]:
                bad.append(index)
                assert all(final_count[g][k] == old_count[g][k] for g in totals
                           for k in ("errors", "repaired", "detected")), "unexpected result change"
            for g in totals:
                totals[g].update(old_count[g])
            key = prompt_key(item["model"], cols, dirty, chunk, constants, item["max_tokens"])
            assert key in witnesses, "prompt key missing from witnesses"
            assert witnesses[key]["spec"] == item["model"] and witnesses[key]["text"] == chunk["output"], "response witness"
            witness_equal += 1
        assert bad == item["final_input_mismatches_0based"], "final-input discrepancy set"
        mismatch[item["model"]] = bad
        for g, count in totals.items():
            assert funcs["metrics"](count) == run["summary"][g], "summary mismatch"
            summary_equal += 1
    assert witness_equal == len(witnesses) == 150, "witness coverage"
    result = {"historical_chunks_equal": historical_equal, "summaries_equal": summary_equal,
              "cache_witnesses_equal": witness_equal, "final_mismatches": mismatch,
              "changed_dirty_cells": sum(x != y for a, b in zip(dirty, final[1]) for x, y in zip(a, b)),
              "changed_clean_cells": sum(x != y for a, b in zip(clean, final[2]) for x, y in zip(a, b)),
              "error_mask_equal": old_errors == new_errors}
    assert result["changed_dirty_cells"] == result["changed_clean_cells"] == 122, "location delta"
    return result


if __name__ == "__main__":
    print(json.dumps(verify_bundle(Path(__file__).resolve().parent), ensure_ascii=False, indent=2))
