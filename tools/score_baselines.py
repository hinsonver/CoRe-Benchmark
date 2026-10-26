#!/usr/bin/env python3
"""Re-score saved baseline outputs, offline; never run a model or Baran training."""
import argparse
import ast
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re

import numpy as np
import pandas as pd

GROUPS = ("all", "identity", "other")
COUNT_KEYS = ("errors", "predicted", "repaired", "detected")
TAG = "custom_deepseek_deepseek-v4-pro"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_minutes(seconds):
    # Preserve numpy's scalar rounding, as in e5_baselines.summarize. Casting to
    # Python float before rounding changes the exact 3-second (0.05 min) tie.
    return float(round(np.mean(seconds) / 60, 1))


def frozen_functions(root):
    """Load only pure scoring definitions, never clients, credentials or model runners."""
    tree = ast.parse((Path(root) / "code/src/probe_clean.py").read_text())
    wanted = {"norm", "metrics", "parse", "score_chunk", "spread_chunks", "total", "f1_of", "bootstrap_diff"}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    if {n.name for n in nodes} != wanted:
        raise ValueError("Missing frozen scoring definitions")
    ns = {"re": re, "json": json, "random": random}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "frozen_baseline_scoring", "exec"), ns)
    for name in ("IDENTITY", "ENTITY"):
        ns[name] = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
    return ns


def read_frame(path, columns=None):
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as stream:
        records = list(csv.reader(stream))
    if not records or not records[0] or len(set(records[0])) != len(records[0]):
        raise ValueError("Invalid CSV header: " + path.name)
    width = len(columns) if columns is not None else len(records[0])
    if any(len(row) != width for row in records):
        raise ValueError("CSV shape/column mismatch: " + path.name)
    return pd.DataFrame(records[1:], columns=list(columns) if columns is not None else records[0])


def score_table(dirty, clean, output, skip, identity, ns):
    if dirty.shape != clean.shape or output.shape != clean.shape:
        raise ValueError("Baseline table shape mismatch")
    if list(dirty.columns) != list(clean.columns) or list(output.columns) != list(clean.columns):
        raise ValueError("Baseline column alignment mismatch")
    if any(type(i) is not int or not 0 <= i < len(clean) for i in skip):
        raise ValueError("Invalid excluded row")
    counts = {g: Counter({k: 0 for k in COUNT_KEYS}) for g in GROUPS}
    norm = ns["norm"]
    for i, (d, c, out) in enumerate(zip(dirty.itertuples(index=False, name=None), clean.itertuples(index=False, name=None), output.itertuples(index=False, name=None))):
        if i in skip:
            continue
        for column, dv, cv, ov in zip(clean.columns, d, c, out):
            error, change = dv != cv, norm(ov) != norm(dv)
            values = {"errors": int(error), "predicted": int(change), "detected": int(error and change),
                      "repaired": int(error and change and norm(ov) == norm(cv))}
            for group in ("all", "identity" if column in identity else "other"):
                counts[group].update(values)
    return {g: ns["metrics"](dict(v)) for g, v in counts.items()}


def checked_fixes(fixes, nrows, columns):
    if not isinstance(fixes, list):
        raise ValueError("Invalid fix list")
    for fix in fixes:
        if (not isinstance(fix, list) or len(fix) != 3 or type(fix[0]) is not int
                or not 0 <= fix[0] < nrows or fix[1] not in columns or not isinstance(fix[2], str)):
            raise ValueError("Invalid fix position/value")
    return fixes


def score_fixes(dirty, clean, fixes, identity, ns):
    checked_fixes(fixes, len(clean), clean.columns)
    # Original P2 rule: last *non-no-op* prediction wins; a subsequent no-op does
    # not cancel an earlier prediction. Reconstruct without reading saved counts.
    output = dirty.copy()
    for i, c, v in fixes:
        if ns["norm"](v.strip()) != ns["norm"](dirty.at[i, c]):
            output.at[i, c] = v.strip()
    got = score_table(dirty, clean, output, set(), identity, ns)
    reference = ns["score_chunk"](dirty, clean, [{"row": i + 1, "column": c, "value": v} for i, c, v in fixes], identity)
    if {g: {k: got[g][k] for k in COUNT_KEYS} for g in GROUPS} != reference:
        raise ValueError("Independent whole-table scorer disagrees with frozen pure scorer")
    return got


def development_indices(dirty, development):
    if len(development) > len(dirty) or development.shape[1] != dirty.shape[1]:
        raise ValueError("Invalid development shape")
    indices = pd.RangeIndex(len(dirty)).to_series().sample(n=len(development), random_state=42).index.tolist()
    if not development.reset_index(drop=True).equals(dirty.iloc[indices].reset_index(drop=True)):
        raise ValueError("Saved development sample values differ from seed42 draw")
    return set(indices)


def compare_values(got, expected, location, differences):
    if isinstance(got, dict) and isinstance(expected, dict):
        for key in sorted(set(got) | set(expected)):
            compare_values(got.get(key), expected.get(key), location + "/" + str(key), differences)
    elif got != expected:
        differences.append({"location": location, "reconstructed": got, "archived": expected})


def score_e5_record(filename, record, dirty, clean, ns):
    match = re.fullmatch(r"(.+)__(perfect|raha)__seed([0-9]+)\.json", filename)
    if not match or any(record.get(k) != v for k, v in zip(("dataset", "mode", "seed"),
                                                          (match[1], match[2], int(match[3])))):
        raise ValueError("E5 filename/record metadata mismatch")
    for k in ("seconds", "corrections", "detected"):
        if not isinstance(record.get(k), (int, float)) or isinstance(record[k], bool) or record[k] < 0:
            raise ValueError("Invalid E5 numeric metadata")
    differences = []
    raw = "fixes" in record
    if raw:
        if len(record["fixes"]) != record["corrections"]:
            raise ValueError("E5 corrections/fixes metadata mismatch")
        metrics = score_fixes(dirty, clean, record["fixes"], set(ns["IDENTITY"][match[1].split("_")[0]]), ns)
    else:
        # This is only an arithmetic check of saved counts, NOT raw validation.
        for group in GROUPS:
            if set(record["counts"][group]) != set(COUNT_KEYS) or any(type(v) is not int or v < 0 for v in record["counts"][group].values()):
                raise ValueError("Invalid archived count-only payload")
        metrics = {g: ns["metrics"](record["counts"][g]) for g in GROUPS}
    for g in GROUPS:
        compare_values({k: metrics[g][k] for k in COUNT_KEYS}, record["counts"][g], filename + "/counts/" + g, differences)
        compare_values(metrics[g], record[g], filename + "/" + g, differences)
    return {"status": "raw_verified" if raw else "archived_count_only", "raw_verified": raw,
            "dataset": match[1], "mode": match[2], "seed": int(match[3]), "metrics": metrics,
            "differences": differences,
            "reason": None if raw else "Historical run did not save fixes; no raw correction validation is possible."}


def label_source(condition, base):
    return condition if condition.endswith("_fresh") else ("beers_orig" if base == "beers" else base)


def validate_labels(labels, nrows):
    if (not isinstance(labels, list) or len(labels) != 20 or len(set(labels)) != 20
            or any(type(i) is not int or not 0 <= i < nrows for i in labels)):
        raise ValueError("Invalid aligned labels: expected 20 distinct in-range row indices")


def score_aligned(dirty, clean, chunks, expected_rows, identity, ns):
    if not isinstance(chunks, list) or len(chunks) != len(expected_rows):
        raise ValueError("Aligned chunk coverage differs")
    result = []
    for ci, (chunk, expected) in enumerate(zip(chunks, expected_rows)):
        if type(chunk.get("chunk")) is not int or chunk["chunk"] != ci:
            raise ValueError("Aligned chunk IDs differ")
        if chunk.get("rows") != expected:
            raise ValueError("Aligned rows differ from frozen spread chunks minus labels")
        fixes = dict(((i, c), v) for i, c, v in checked_fixes(chunk["fixes"], len(clean), clean.columns))
        if any(i not in expected for i, _ in fixes):
            raise ValueError("Aligned fix refers to excluded/unshown row")
        if "output" in chunk:
            parsed = []
            for prediction in ns["parse"](chunk["output"]):
                try:
                    local = int(prediction["row"]) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= local < len(expected) and prediction["column"] in clean.columns:
                    parsed.append([expected[local], prediction["column"], str(prediction["value"]).strip()])
            if parsed != chunk["fixes"]:
                raise ValueError("Aligned saved fixes differ from parsed saved reply")
        counts = {g: Counter({k: 0 for k in COUNT_KEYS}) for g in GROUPS}
        for i in expected:
            for c in clean.columns:
                if dirty.at[i, c] == clean.at[i, c]:
                    continue
                value = fixes.get((i, c))
                change = value is not None and ns["norm"](value) != ns["norm"](dirty.at[i, c])
                count = {"errors": 1, "predicted": int(change), "detected": int(change),
                         "repaired": int(change and ns["norm"](value) == ns["norm"](clean.at[i, c]))}
                for group in ("all", "identity" if c in identity else "other"):
                    counts[group].update(count)
        result.append({"counts": {g: dict(c) for g, c in counts.items()}})
    return result


def aligned_record(stem, dirty, clean, saved, expected_rows, identity, ns):
    """Retain legacy unseeded metadata mismatches, never accept selected-run mismatches."""
    selected = not stem.startswith("baran__") or bool(re.search(r"__run[0-9]+$", stem))
    actual = [ch.get("rows") for ch in saved] if isinstance(saved, list) else None
    mismatch = actual != expected_rows
    if mismatch and not selected:
        # Report only valid historical row-index metadata. No label repair or
        # source mutation is performed; counts refer to its *saved* rows only.
        if not isinstance(actual, list) or len(actual) != len(expected_rows) or any(not isinstance(row, list) for row in actual):
            raise ValueError("Invalid legacy aligned rows")
        flat = [i for rows in actual for i in rows]
        if len(set(flat)) != len(flat) or any(type(i) is not int or not 0 <= i < len(clean) for i in flat):
            raise ValueError("Invalid legacy aligned rows")
        chunks = score_aligned(dirty, clean, saved, actual, identity, ns)
    else:
        chunks = score_aligned(dirty, clean, saved, expected_rows, identity, ns)
    record = {"status": "historical_row_metadata_mismatch" if mismatch else "raw_verified",
              "raw_verified": not mismatch, "selected_for_frozen_comparison": selected,
              "chunks": len(chunks), "scored_rows": sum(len(ch["rows"]) for ch in saved),
              "metrics": {g: ns["metrics"](ns["total"](chunks, g)) for g in GROUPS}}
    if mismatch:
        expected_set = {i for rows in expected_rows for i in rows}
        actual_set = {i for rows in actual for i in rows}
        record["metadata_discrepancy"] = {"mismatched_chunks": sum(a != e for a, e in zip(actual, expected_rows)),
                                           "unexpected_scored_rows": len(actual_set - expected_set),
                                           "missing_scored_rows": len(expected_set - actual_set),
                                           "frozen_comparison_uses_this_archive": False,
                                           "metrics_scope": "saved historical rows only; current labels not validated"}
    return record, chunks


class Evidence:
    """Require exact historical bindings, even if the package's current manifest is regenerated."""
    def __init__(self, root, historical_root=None, authorization_record=None):
        self.root = Path(root).resolve()
        sources = json.loads((self.root / "data/manifests/CORE_SOURCES.json").read_text())
        self.bindings = dict(sources["original_files"])
        self.bindings.update(json.loads((self.root / "data/manifests/RAYYAN_REPLAY.json").read_text())["files"])
        self.private_bindings = sources["private_files"]
        self.private = Path(historical_root).resolve() if historical_root else None
        self.used = {}
        self.authorization = None
        if bool(historical_root) != bool(authorization_record):
            raise ValueError("Historical root and authorization record must be supplied together")
        if self.private:
            path = self.root / "code/src/core_runtime.py"
            spec = importlib.util.spec_from_file_location("baseline_core_runtime", path)
            runtime = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(runtime)
            self.authorization = runtime.preflight_private(self.root, self.private, authorization_record)

    def path(self, relative):
        rel = Path(relative)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unsafe evidence path")
        private = relative in self.private_bindings
        if private and self.private is None:
            raise ValueError("Historical Movies raw inputs require explicit authorization")
        root = self.private if private else self.root
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError("Missing baseline dependency: " + relative)
        cursor = path
        while cursor != root:
            if cursor.is_symlink():
                raise ValueError("Evidence symlink forbidden: " + relative)
            cursor = cursor.parent
        expected = (self.private_bindings if private else self.bindings).get(relative)
        if expected is None or digest(path) != expected:
            raise ValueError("Baseline dependency hash mismatch: " + relative)
        self.used[relative] = expected
        return path

    def json(self, relative):
        return json.loads(self.path(relative).read_text())

    def frame(self, relative, columns=None):
        return read_frame(self.path(relative), columns)

    def tables(self, condition):
        clean = self.frame(f"data/final/{condition}/clean.csv")
        dirty = self.frame(f"data/final/{condition}/dirty.csv", clean.columns)
        if dirty.shape != clean.shape:
            raise ValueError("Frozen dirty/clean shape mismatch")
        return dirty, clean

    def aligned_seeded_inventory(self, conditions):
        """Match frozen consumers' run* glob, then require the exact bound seeds.

        Checking only run0..2 paths would silently ignore run3 or runodd files that
        aligned.py/paper_tables/figures include in the frozen comparison instead.
        Movies' public numerical witnesses do not substitute for authorized raw files.
        """
        directory = "artifacts/raw_outputs/aligned"
        selected = {}
        for condition in conditions:
            prefix = directory + f"/baran__{condition}__run"
            expected = {prefix + str(k) + ".json" for k in range(3)}

            def bound_runs(bindings):
                return {name for name in bindings if name.startswith(prefix) and name.endswith(".json")}

            if bound_runs(self.bindings) != expected:
                raise ValueError("Aligned seeded binding inventory differs: " + condition)
            private = condition.split("_")[0] == "movies"
            if private and (self.private is None or bound_runs(self.private_bindings) != expected):
                raise ValueError("Aligned seeded private inventory differs: " + condition)
            source_root = self.private if private else self.root
            physical = {path.relative_to(source_root).as_posix()
                        for path in (source_root / directory).glob(f"baran__{condition}__run*.json")}
            if physical != expected:
                raise ValueError("Aligned seeded physical inventory differs: " + condition)
            selected[condition] = sorted(expected)
            for name in selected[condition]:
                self.path(name)
        return selected


def replay(root, historical_root=None, authorization_record=None):
    evidence = Evidence(root, historical_root, authorization_record)
    bases = ["hospital", "beers"] + (["movies"] if historical_root else [])
    conditions = [c for base in bases for c in ["beers_orig" if base == "beers" else base,
                                               base + "_fresh", base + "_surrogatewords", base + "_surrogate"]]
    selected_runs = evidence.aligned_seeded_inventory(conditions)
    evidence.path("code/src/probe_clean.py")
    ns = frozen_functions(root)
    differences, tabclean, baran, aligned = [], {}, {}, {}
    e4 = evidence.json("artifacts/raw_outputs/e4/summary.json")
    for condition in conditions + ["rayyan"]:
        prefix = "artifacts/raw_outputs/e4/"
        clean = evidence.frame(prefix + f"inputs/{condition}/clean.csv")
        dirty = evidence.frame(prefix + f"inputs/{condition}/dirty.csv", clean.columns)
        output = evidence.frame(prefix + f"tabclean/{condition}/final_cleaned.csv", clean.columns)
        dev = evidence.frame(prefix + f"tabclean/{condition}/dev_dirty.csv", clean.columns)
        if condition != "rayyan":
            expected_dirty, expected_clean = evidence.tables(condition)
            if not dirty.equals(expected_dirty) or not clean.equals(expected_clean):
                raise ValueError("TabClean inputs differ from frozen condition: " + condition)
        skip = development_indices(dirty, dev)
        got = {"scored_rows": len(clean) - len(skip), "dev_rows": len(skip),
               **score_table(dirty, clean, output, skip, set(ns["IDENTITY"][condition.split("_")[0]]), ns)}
        if condition == "rayyan":
            # Rayyan's actual TabClean input version is deliberately not the audit table.
            sample = evidence.json("data/provenance/rayyan/dev-row-indices.json")
            if skip != set(sample["indices_0based_in_sample_order"]):
                raise ValueError("Rayyan development indices differ")
            expected = {"scored_rows": 850, "dev_rows": 150,
                        "all": ns["metrics"]({"errors": 808, "predicted": 498, "detected": 497, "repaired": 461})}
            compare_values({k: got[k] for k in expected}, expected, "e4/rayyan", differences)
        else:
            compare_values(got, e4[condition], "e4/" + condition, differences)
        tabclean[condition] = {"status": "raw_verified", "raw_verified": True, **got}

    summaries = evidence.json("artifacts/raw_outputs/e5/summary.json")
    names = sorted(name for name in evidence.bindings if re.fullmatch(r"artifacts/raw_outputs/e5/.+__(perfect|raha)__seed[0-9]+\.json", name)
                   and (historical_root or "/movies" not in name))
    groups = defaultdict(list)
    for name in names:
        saved = evidence.json(name)
        dirty, clean = evidence.tables(saved["dataset"])
        got = score_e5_record(Path(name).name, saved, dirty, clean, ns)
        differences.extend(got.pop("differences"))
        baran[Path(name).name] = got
        groups[saved["dataset"] + "|" + saved["mode"]].append((got, saved["seconds"]))
    summary_checks = {}
    for key, runs in groups.items():
        vals = {g: [r["metrics"][g]["repair_f1"] for r, _ in runs] for g in GROUPS}
        got = {"seeds": len(runs), **{g + "_repair_f1": round(float(np.mean(v)), 3) for g, v in vals.items()},
               **{g + "_sd": round(float(np.std(v)), 3) for g, v in vals.items()},
               "minutes": runtime_minutes([seconds for _, seconds in runs])}
        compare_values(got, summaries[key], "e5/summary/" + key, differences)
        summary_checks[key] = {"raw_runs": sum(r["raw_verified"] for r, _ in runs), "count_only_runs": sum(not r["raw_verified"] for r, _ in runs), **got}

    aligned_summaries = {}
    for base in bases:
        labels = evidence.json(f"artifacts/raw_outputs/aligned/labels_{base}.json")
        original = "beers_orig" if base == "beers" else base
        if set(labels) != {original, base + "_fresh"}:
            raise ValueError("Aligned label source metadata differs")
        comparison = evidence.json(f"artifacts/raw_outputs/aligned/compare__{base}__{TAG}.json")
        for condition in [original, base + "_fresh", base + "_surrogatewords", base + "_surrogate"]:
            dirty, clean = evidence.tables(condition)
            labeled = labels[label_source(condition, base)]
            validate_labels(labeled, len(clean))
            expected_rows = [[i for i in ch if i not in labeled] for ch in ns["spread_chunks"](clean, ns["ENTITY"][base], 20)]
            chunks_by_name = {}
            seeded_stems = [Path(name).stem for name in selected_runs[condition]]
            for stem in [f"baran__{condition}"] + seeded_stems + [f"{TAG}__{condition}"]:
                saved = evidence.json(f"artifacts/raw_outputs/aligned/{stem}.json")
                record, chunks = aligned_record(stem, dirty, clean, saved, expected_rows, set(ns["IDENTITY"][base]), ns)
                chunks_by_name[stem] = chunks
                record["labeled_rows"] = len(labeled)
                aligned[stem + ".json"] = record
                if not record["raw_verified"]:
                    differences.append({"location": "aligned/" + stem + "/row_metadata",
                                        "reconstructed": 0, "archived": record["metadata_discrepancy"]["mismatched_chunks"],
                                        "classification": "legacy_unseeded_not_selected_for_frozen_comparison"})
            for group in GROUPS:
                bs = [chunks_by_name[stem] for stem in seeded_stems]
                llm = chunks_by_name[f"{TAG}__{condition}"]
                f1s = [ns["f1_of"](b, group) for b in bs]
                _, lo, hi = ns["bootstrap_diff"](llm, bs[0], group, paired=True)
                mean = sum(f1s) / len(f1s)
                got = {"baran": round(mean, 3), "baran_runs": [round(v, 3) for v in f1s],
                       "llm": round(ns["f1_of"](llm, group), 3),
                       "llm_minus_baran": [round(ns["f1_of"](llm, group) - mean, 3), round(lo, 3), round(hi, 3)]}
                key = condition + "|" + group
                compare_values(got, comparison[key], "aligned/" + key, differences)
                aligned_summaries[key] = got

    missing = [name for name, value in baran.items() if not value["raw_verified"]]
    metadata_mismatches = [name for name, value in aligned.items() if not value["raw_verified"]]
    selection_sources = ["code/src/aligned.py", "code/src/paper_tables.py", "code/src/paper_tables_frozen.py", "code/src/figures.py"]
    return {"schema_version": 1, "mode": "authorized_historical" if historical_root else "public_raw_only",
            "status": "matches_with_explicit_raw_coverage_gaps" if not differences else "archived_differences_detected",
            "no_generation_training_or_network_calls": True, "frozen_results_modified": False,
            "coverage": {"tabclean_raw_conditions": len(tabclean), "e5_raw_runs": len(baran) - len(missing),
                         "e5_count_only_runs": len(missing), "aligned_raw_archives": len(aligned) - len(metadata_mismatches),
                         "aligned_archives_inspected": len(aligned), "aligned_historical_metadata_mismatches": metadata_mismatches,
                         "e5_missing_fixes": missing,
                         "movies_raw": ("verified_selected_runs_with_legacy_metadata_exception" if metadata_mismatches else "verified_from_exact_authorized_history") if historical_root else "excluded_not_raw_verified",
                         "public_movies_numerical_witnesses": "not_used_as_raw_validation"},
            "tabclean": tabclean, "whole_table_baran": baran, "e5_summaries": summary_checks,
            "aligned": aligned, "aligned_summaries": aligned_summaries, "differences": differences,
            "legacy_selection_provenance": {"rule": "All existing __run*.json files take precedence; unseeded is fallback only. Three bound seeded files required for every condition in this replay.",
                                            "frozen_result_map_labels": ["fig:aligned", "tab:aligned"],
                                            "source_sha256": {name: digest(Path(root) / name) for name in selection_sources},
                                            "selected_frozen_comparison_differences": [d for d in differences if d.get("classification") != "legacy_unseeded_not_selected_for_frozen_comparison"]},
            "authorization": evidence.authorization, "source_sha256": evidence.used,
            "scoring": {"normalization": "frozen case/whitespace/comma normalization", "development_draw": "pandas seed42, full sample values checked",
                        "aligned_labels": "saved 20 labels; original reused for both surrogates; fresh uses fresh labels",
                        "rayyan_inputs": "saved actual TabClean inputs, not audit-table substitution",
                        "aligned_interval": "frozen paired 2000-replicate bootstrap against first Baran run"}}


def safe_report(value):
    forbidden = {"fixes", "output", "examples", "truth", "pred", "answer", "tconst", "nconst", "real_orig"}
    if isinstance(value, dict):
        if forbidden & value.keys():
            raise ValueError("Raw record payload forbidden in baseline report")
        for child in value.values():
            safe_report(child)
    elif isinstance(value, list):
        for child in value:
            safe_report(child)
    elif isinstance(value, str) and re.search(r"\b(?:tt|nm)\d{7,}\b", value):
        raise ValueError("Raw identifier payload forbidden in baseline report")


def write_report(output, report):
    output = Path(output)
    safe_report(report)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "baseline-scores.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory beneath this package's build directory")
    parser.add_argument("--historical-root", type=Path)
    parser.add_argument("--authorization-record", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if root / "build" not in output.parents:
        parser.error("--output must be a new directory beneath the package build directory")
    if output.exists():
        raise FileExistsError("Refusing to overwrite existing baseline output")
    report = replay(root, args.historical_root, args.authorization_record)
    write_report(output, report)
    print(json.dumps({"status": report["status"], "coverage": report["coverage"], "differences": len(report["differences"])}, indent=2))
    return 2 if report["differences"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
