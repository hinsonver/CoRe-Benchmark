"""Rejudge frozen row-continuation replies offline; never call a model client."""
import argparse
import ast
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import random
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ("model", "dataset", "source", "named", "n", "k", "seed", "error_rows")
PUBLIC_DATASETS = {"beers", "flights", "hospital", "rayyan", "tax"}
# Canonical AST extracted from the original code/src/data.py whose full-file
# SHA256 is already bound by CORE_SOURCES.private_code (the adapted loader differs).
COUNTER_COLUMNS_SOURCE_SHA256 = "a27640d779e49f15f38618b7fe63d6bfc06402e31831bfc900d05f603d257a7d"
COUNTER_COLUMNS_AST_SHA256 = "7f35eefb9a5e4d810b23660ab9a109efd69326678c0e9e39eda4d699605d4fef"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pure_helpers(root):
    """Compile only frozen pure function ASTs, not imports or generation entry points.

    Importing probe_rowcont would import src.clients. Its cache/environment behavior
    is irrelevant to scoring, so no statement from either module is executed except
    these explicitly named function definitions.
    """
    namespace = {"collections": collections, "csv": csv, "io": io, "pd": pd}
    for relative, names in (
        ("code/src/probe_rowcont.py", {"parse_row", "structural_baselines", "_top", "structural_guesses"}),
        ("code/src/data.py", {"counter_columns"}),
    ):
        path = Path(root) / relative
        tree = ast.parse(path.read_text())
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        if {node.name for node in selected} != names:
            raise ValueError("Missing frozen pure scoring helper")
        module = ast.Module(body=selected, type_ignores=[])
        if relative == "code/src/data.py":
            fingerprint = hashlib.sha256(ast.dump(module, include_attributes=False).encode("utf-8")).hexdigest()
            if fingerprint != COUNTER_COLUMNS_AST_SHA256:
                raise ValueError("Frozen counter_columns AST hash mismatch")
        exec(compile(module, str(path), "exec"), namespace)
    return namespace


def sample_rows(dirty, clean, config):
    """Rebuild the frozen hundred-sample prefix, including error-row filtering."""
    n, k, seed = (config[key] for key in ("n", "k", "seed"))
    if any(type(x) is not int for x in (n, k, seed)) or n < 1 or k < 1 or k >= len(clean):
        raise ValueError("Invalid sampling configuration")
    if type(config["error_rows"]) is not bool:
        raise ValueError("Invalid error_rows configuration")
    pool = list(range(k, len(clean)))
    if config["error_rows"]:
        has_error = dirty.ne(clean).any(axis=1)
        pool = [i for i in pool if has_error.iloc[i]]
    if not pool:
        raise ValueError("Empty sampling pool")
    return random.Random(seed).sample(pool, min(max(n, 100), len(pool)))[:n]


def compare_summaries(saved, actual, private=False):
    """Compare every archived leaf, without exporting differing source values."""
    result = {"fields_compared": 0, "mismatches": [],
              "missing_archived_fields": sorted(set(actual) - set(saved))}

    def walk(left, right, field):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                child = field + "." + key
                if key not in left or key not in right:
                    mismatch(child, "missing_field")
                else:
                    walk(left[key], right[key], child)
            return
        result["fields_compared"] += 1
        if type(left) is not type(right) or left != right:
            mismatch(field, "value_or_type")

    def mismatch(field, kind):
        if private and field.startswith("summary.per_column"):
            field = "summary.per_column.[redacted-column]"
        result["mismatches"].append({"field": field, "kind": kind})

    for key in sorted(saved):
        if key not in actual:
            mismatch("summary." + (key if not private else "[unrecognized-field]"), "unrecognized_field")
        else:
            walk(saved[key], actual[key], "summary." + key)
    return result


def rescore_archive(archive, dirty, clean, helpers=None, baselines=None, private=False):
    """Reconstruct all summary fields from saved text and aligned original frames."""
    if not isinstance(archive, dict) or not isinstance(archive.get("summary"), dict):
        raise ValueError("Missing archive summary configuration")
    saved = archive["summary"]
    if any(key not in saved for key in CONFIG):
        raise ValueError("Incomplete archive configuration")
    config = {key: saved[key] for key in CONFIG}
    if config["source"] not in {"clean", "dirty"} or type(config["named"]) is not bool:
        raise ValueError("Invalid source/named configuration")
    if not isinstance(config["model"], str) or not isinstance(config["dataset"], str):
        raise ValueError("Invalid model/dataset configuration")
    if dirty.shape != clean.shape or list(dirty.columns) != list(clean.columns):
        raise ValueError("Unaligned source tables")
    starts = sample_rows(dirty, clean, config)
    trials = archive.get("trials")
    if not isinstance(trials, list) or any(not isinstance(t, dict) for t in trials):
        raise ValueError("Missing or malformed saved trials; summary fallback forbidden")
    if [t.get("row") for t in trials] != starts:
        raise ValueError("Saved trial rows differ from reconstructed sampling")
    helpers = helpers or pure_helpers(ROOT)
    ctx_df = dirty if config["source"] == "dirty" else clean
    skip = set(helpers["counter_columns"](clean))
    if baselines is None:
        base = helpers["structural_baselines"](ctx_df)
        cbase = base if config["source"] == "clean" else helpers["structural_baselines"](clean)
    else:
        base, cbase = baselines
    freq, trans, _ = base
    top, guesses = helpers["_top"], helpers["structural_guesses"]
    agg = {key: [0, 0] for key in ("inf", "noninf", "hard", "leak", "leak_hard")}
    agg.update(exact=0, parsed=0, failed=0, unparseable=0)
    per_col = collections.defaultdict(collections.Counter)
    flag_mismatches = 0
    for row_number, trial in zip(starts, trials):
        if not isinstance(trial.get("output"), str) or type(trial.get("parsed")) is not bool:
            raise ValueError("Malformed saved trial output/parsed flag")
        failed = "error" in trial
        if failed:
            if not isinstance(trial["error"], str) or trial["output"] != "":
                raise ValueError("Malformed failed-call trial")
            agg["failed"] += 1
            pred = None
        else:
            pred = helpers["parse_row"](trial["output"], clean.shape[1])
            agg["unparseable"] += pred is None
        flag_mismatches += trial["parsed"] != (pred is not None)
        if pred is None:
            continue
        agg["parsed"] += 1
        ctx = ctx_df.iloc[row_number - config["k"]:row_number]
        truth, dtruth = clean.iloc[row_number].tolist(), dirty.iloc[row_number].tolist()
        target_row = dtruth if config["source"] == "dirty" else truth
        agg["exact"] += pred == target_row
        for j, col in enumerate(clean.columns):
            if col in skip:
                continue
            seen = set(ctx[col])
            target = target_row[j]
            bucket = "inf" if target in seen else "noninf"
            agg[bucket][0] += pred[j] == target
            agg[bucket][1] += 1
            if bucket == "noninf":
                f_ok = top(freq[col], target) == target
                t_ok = top(trans[col].get(ctx[col].iloc[-1], {}), target) == target
                s_ok = target in guesses(col, ctx.iloc[-1], ctx_df.iloc[row_number], base)
                pc = per_col[col]
                pc["n"] += 1
                pc["model"] += pred[j] == target
                pc["freq"] += f_ok
                pc["trans"] += t_ok
                pc["structural"] += s_ok
                if not s_ok:
                    agg["hard"][0] += pred[j] == target
                    agg["hard"][1] += 1
            if config["source"] == "dirty" and dtruth[j] != truth[j] and truth[j] not in seen:
                agg["leak"][0] += pred[j] == truth[j]
                agg["leak"][1] += 1
                if truth[j] not in guesses(col, clean.iloc[row_number - 1], clean.iloc[row_number], cbase):
                    agg["leak_hard"][0] += pred[j] == truth[j]
                    agg["leak_hard"][1] += 1

    def rate(value):
        return round(value[0] / value[1], 4) if value[1] else None

    summary = dict(config, skipped_counter_cols=sorted(skip),
                   parse_rate=round(agg["parsed"] / len(starts), 4),
                   exact_row_match=round(agg["exact"] / len(starts), 4),
                   failed_calls=agg["failed"], acc_inferable=rate(agg["inf"]),
                   acc_noninferable=rate(agg["noninf"]), noninferable_cells=agg["noninf"][1],
                   acc_hard=rate(agg["hard"]), hard_cells=agg["hard"][1],
                   leak_rate=rate(agg["leak"]), leak_cells=agg["leak"][1],
                   leak_hard_rate=rate(agg["leak_hard"]), leak_hard_cells=agg["leak_hard"][1])
    summary["per_column"] = {
        col: dict(n=v["n"], **{key: round(v[key] / v["n"], 3)
                               for key in ("model", "freq", "trans", "structural")})
        for col, v in per_col.items() if v["n"]}
    return {"summary": summary, "counts": agg,
            "trial_checks": {"trials": len(trials), "sampling_matches": True,
                             "parsed_flag_mismatches": flag_mismatches},
            "comparison": compare_summaries(saved, summary, private)}


def bound_file(root, relative, bindings):
    root = Path(root).resolve()
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or relative not in bindings:
        raise ValueError("Unbound or unsafe source dependency")
    path = root / rel
    if any(p.is_symlink() for p in (path, *path.parents) if p != root.parent):
        raise ValueError("Source dependency symlinks forbidden")
    if not path.is_file() or digest(path) != bindings[relative]:
        raise ValueError("Source dependency hash mismatch: " + relative)
    return path


def archive_paths(root):
    return sorted(path for path in (Path(root) / "artifacts/raw_outputs/p1").glob("*.json")
                  if "movies" not in path.name)


def validate_output_path(root, output, historical_root=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Output already exists; no overwrite")
    if output == root or output in root.parents:
        raise ValueError("Output must not contain the package source")
    if root in output.parents and (root / "build") not in output.parents:
        raise ValueError("Package-local output must be below build, never source directories")
    if historical_root is not None:
        historical = Path(historical_root).resolve()
        if output == historical or historical in output.parents or output in historical.parents:
            raise ValueError("Output must not overlap historical sources")
    return output


def run(root, output, historical_root=None, authorization_record=None):
    root = Path(root).resolve()
    if (historical_root is None) != (authorization_record is None):
        raise ValueError("historical-root and authorization-record must be supplied together")
    output = validate_output_path(root, output, historical_root)
    manifest = json.loads((root / "data/manifests/CORE_SOURCES.json").read_text())
    # The frozen probe is byte-identical in the statistical-core adaptation.
    bound_file(root, "code/src/probe_rowcont.py", manifest["private_code"])
    helpers = pure_helpers(root)
    sources = [(path.relative_to(root).as_posix(), root, False)
               for path in archive_paths(root)]
    expected_public = {p for p in manifest["original_files"]
                       if p.startswith("artifacts/raw_outputs/p1/") and "movies" not in p}
    if {p for p, _, _ in sources} != expected_public:
        raise ValueError("Included continuation archive inventory differs from original binding")
    private_check = None
    if historical_root is not None:
        # This module has no clients/data-loader imports and performs no I/O on import.
        import importlib.util
        spec = importlib.util.spec_from_file_location("continuation_private_runtime", root / "code/src/core_runtime.py")
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        private_check = runtime.preflight_private(root, historical_root, authorization_record)
        historical_root = Path(historical_root).resolve()
        for relative in ("code/src/probe_rowcont.py", "code/src/data.py"):
            bound_file(historical_root, relative, manifest["private_code"])
        # Extract the historical counter helper too, not the adapted table loader.
        historical_helpers = pure_helpers(historical_root)
        sources += [(p, historical_root, True) for p in sorted(manifest["private_files"])
                    if p.startswith("artifacts/raw_outputs/p1/") and p.endswith(".json")]

    frames, baselines, input_hashes, records = {}, {}, {}, []
    for relative, source_root, private in sources:
        bindings = manifest["private_files"] if private else manifest["original_files"]
        path = bound_file(source_root, relative, bindings)
        archive = json.loads(path.read_text())
        dataset = archive["summary"]["dataset"]
        if dataset not in ({"movies_1"} if private else PUBLIC_DATASETS):
            raise ValueError("Unexpected dataset in bound continuation archive")
        if dataset not in frames:
            loaded = []
            for kind in ("dirty", "clean"):
                name = "data/final/" + dataset + "/" + kind + ".csv"
                table = bound_file(source_root, name, bindings)
                input_hashes[name] = digest(table)
                # Tax is capped at its original first 5,000 rows, before sampling.
                loaded.append(pd.read_csv(table, dtype=str, keep_default_na=False,
                                          nrows=5000 if dataset == "tax" else None))
            dirty, clean = loaded
            if dirty.shape != clean.shape:
                raise ValueError("Source table shape mismatch")
            dirty.columns = clean.columns
            frames[dataset] = dirty.reset_index(drop=True), clean.reset_index(drop=True)
        dirty, clean = frames[dataset]
        active = historical_helpers if private else helpers
        for source, frame in (("dirty", dirty), ("clean", clean)):
            if (dataset, source) not in baselines:
                baselines[dataset, source] = active["structural_baselines"](frame)
        source = archive["summary"]["source"]
        result = rescore_archive(archive, dirty, clean, active,
                                 (baselines[dataset, source], baselines[dataset, "clean"]), private)
        if private:
            # Preserve every numeric summary component but replace table headers by
            # stable positions. No raw reply, row, cell, or header is written.
            columns = {col: "column_" + str(i + 1) for i, col in enumerate(clean.columns)}
            summary = result["summary"]
            summary["skipped_counter_cols"] = [columns[c] for c in summary["skipped_counter_cols"]]
            summary["per_column"] = {columns[c]: value for c, value in summary["per_column"].items()}
        records.append(dict(archive=relative, archive_sha256=digest(path),
                            mode="authorized_historical" if private else "included_raw", **result))
    report = {
        "schema_version": 1, "mode": "saved_raw_trial_rejudgment", "new_model_calls": 0,
        "summary_fallback": False, "raw_movie_records_exported": 0,
        "included_archives": sum(not private for _, _, private in sources),
        "historical_movie_archives": sum(private for _, _, private in sources),
        "trials": sum(r["trial_checks"]["trials"] for r in records),
        "summary_mismatch_archives": sum(bool(r["comparison"]["mismatches"]) for r in records),
        "parsed_flag_mismatches": sum(r["trial_checks"]["parsed_flag_mismatches"] for r in records),
        "legacy_schema_omission_archives": sum(bool(r["comparison"]["missing_archived_fields"]) for r in records),
        "failed_calls": sum(r["counts"]["failed"] for r in records),
        "unparseable_replies": sum(r["counts"]["unparseable"] for r in records),
        "historical_validation": private_check,
        "movie_raw_rejudgment_status": "completed" if private_check else "not_requested_requires_external_history_and_authorization",
        "input_sha256": input_hashes,
        "scoring_source_sha256": {p: digest(root / p) for p in
                                  ("code/src/probe_rowcont.py", "code/src/data.py", "tools/score_continuations.py")},
        "archives": records,
    }
    # Only create the new destination after every source has been validated/scored.
    output.mkdir(parents=True, exist_ok=False)
    (output / "continuation-scores.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    with (output / "continuation-scores.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["archive", "dataset", "trials", "parse_rate", "exact_row_match", "hard_cells",
                         "acc_hard", "failed_calls", "summary_mismatches", "parsed_flag_mismatches"])
        for record in records:
            summary = record["summary"]
            writer.writerow([record["archive"], summary["dataset"], record["trial_checks"]["trials"],
                             summary["parse_rate"], summary["exact_row_match"], summary["hard_cells"],
                             summary["acc_hard"], summary["failed_calls"],
                             len(record["comparison"]["mismatches"]), record["trial_checks"]["parsed_flag_mismatches"]])
    return {key: value for key, value in report.items() if key != "archives"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("build/raw-continuations"))
    parser.add_argument("--historical-root", type=Path)
    parser.add_argument("--authorization-record", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    result = run(root, output, args.historical_root, args.authorization_record)
    print(json.dumps(result, sort_keys=True))
    if result["summary_mismatch_archives"] or result["parsed_flag_mismatches"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
