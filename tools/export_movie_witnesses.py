"""Read private frozen Movies evidence and export numerical witnesses only.

No model calls, data generation, or writes are performed. Runtime consumers need
only the resulting JSON and the standard library; pandas is an export dependency.
The caller must verify its private-input hash manifest before invoking export.
"""
import collections
from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import sys

MODEL = "custom_deepseek_deepseek-v4-pro"
CONDS = ("movies", "movies_fresh", "movies_surrogatewords", "movies_surrogate")


@contextmanager
def _original_modules(source):
    """Load original scoring code in a separate namespace without bytecode writes."""
    prefix = "_core_private_witness"
    settings = {"CORE_ARTIFACT_ROOT": str(source),
                "CORE_P2_DIR": str(source / "artifacts/raw_outputs/p2"),
                "CORE_NEAR_DIR": str(source / "artifacts/raw_outputs/near"),
                "CORE_CACHE_FILE": str(source / "build/disabled-witness-cache.jsonl")}
    previous = {k: os.environ.get(k) for k in settings}
    bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    os.environ.update(settings)
    try:
        location = source / "code/src/__init__.py"
        spec = importlib.util.spec_from_file_location(prefix, location,
                    submodule_search_locations=[str(location.parent)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[prefix] = package
        spec.loader.exec_module(package)
        modules = {name: importlib.import_module(f"{prefix}.{name}") for name in
                   ("data", "probe_clean", "aligned", "near_entities", "movies_variants", "screening")}
        # A defensive guard if a future refactor accidentally enters a run path.
        def forbidden(*args, **kwargs):
            raise RuntimeError("Witness export must not call a model")
        clients = sys.modules[f"{prefix}.clients"]
        clients.complete = clients.complete_json = forbidden
        for mod in modules.values():
            for attr in ("complete", "complete_json"):
                if hasattr(mod, attr):
                    setattr(mod, attr, forbidden)
        yield modules
    finally:
        for name in list(sys.modules):
            if name == prefix or name.startswith(prefix + "."):
                del sys.modules[name]
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        sys.dont_write_bytecode = bytecode


def _numeric(value):
    """Keep numeric leaves; dictionary keys are schema/model/dataset identifiers."""
    if isinstance(value, dict):
        return {k: _numeric(v) for k, v in value.items()
                if k not in {"output", "fixes", "examples"} and
                (isinstance(v, (dict, list, int, float, bool)) or v is None)}
    if isinstance(value, list):
        return [_numeric(v) for v in value if isinstance(v, (dict, list, int, float, bool)) or v is None]
    return value


def rates_from_events(events, only_known=False, n_boot=2000):
    """Original entity bootstrap (seed 0), independently reproducible from flags."""
    groups = collections.defaultdict(dict)
    for event in events:
        if only_known and not event["known"]:
            continue
        groups[event["setting"]][event["entity"]] = event["key_hits"]
    out = {}
    for setting, entities in sorted(groups.items()):
        means = [sum(hits) / len(hits) for hits in entities.values()]
        rng = random.Random(0)
        boot = sorted(sum(rng.choice(means) for _ in means) / len(means) for _ in range(n_boot))
        out[setting] = {"rate": round(sum(means) / len(means), 3),
                        "ci": [round(boot[int(.025 * n_boot)], 3), round(boot[int(.975 * n_boot) - 1], 3)],
                        "entities": len(means)}
    return out


def _p2(value, modules, frames):
    pc = modules["probe_clean"]
    cond = value["summary"]["dataset"]
    if cond not in frames:
        frames[cond] = modules["data"].load(cond)
    dirty, clean = frames[cond]
    chunks = []
    for ch in value["chunks"]:
        rows = ch["rows"]
        counts = pc.score_chunk(dirty.iloc[rows].reset_index(drop=True),
                                clean.iloc[rows].reset_index(drop=True), pc.parse(ch["output"]), pc.IDENTITY["movies"])
        if counts != ch["counts"]:
            raise ValueError(f"Archived P2 counts disagree with saved reply: {cond}")
        chunks.append({"start": int(ch["start"]), "rows": [int(i) for i in rows],
                       "counts": counts, "truncated": False})
        # Match clients.truncated without retaining the reply in the witness.
        text = ch["output"].strip()
        chunks[-1]["truncated"] = not text or not text.endswith(("}", "```"))
    for group in ("all", "identity", "other"):
        if pc.metrics(pc.total(chunks, group)) != value["summary"][group]:
            raise ValueError(f"Archived P2 summary disagrees with counts: {cond}/{group}")
    return {"summary": value["summary"], "chunks": chunks}


def _near(model, source, modules, read):
    ne, pc = modules["near_entities"], modules["probe_clean"]
    plan = read(source / "data/final/_near/movies/plan.json")
    if plan["targets"] != 57 or len(plan["plan"]) != 57:
        raise ValueError("Frozen Movies target pool must contain exactly 57 entities")
    summary = _numeric(read(source / f"artifacts/raw_outputs/near/{model}__movies__summary.json"))
    known = ne.known_names("movies", model)
    modules["screening"].known_key_rates(source / "data/final/_near", "movies", model, summary)
    tables = {t: modules["data"].load(f"_near/movies/{t}")[1] for t in ne.TYPES}
    targets = {i: (ordinal, p) for ordinal, p in enumerate(plan["plan"]) for i in p["rows"]}
    groups = collections.OrderedDict()
    for record in read(source / f"artifacts/raw_outputs/near/{model}__movies.json"):
        rows = plan["chunk_rows"][record["support"]][record["chunk"]]
        setting = "|".join((record["type"], record["support"], record["prompt"]))
        column = ne.KEY_COLUMN[("movies", "real" if record["type"] == "control" else record["type"])]
        edits = {}
        for pred in pc.parse(record["output"]):
            try:
                edits[(int(pred["row"]) - 1, str(pred["column"]))] = str(pred["value"])
            except (TypeError, ValueError):
                continue
        clean = tables[record["type"]]
        for j, i in enumerate(rows):
            if i not in targets:
                continue
            ordinal, target = targets[i]
            event = groups.setdefault((setting, ordinal), {"setting": setting, "entity": ordinal,
                "known": target["famous"]["name"] in known, "key_hits": [], "cells": []})
            v = edits.get((j, column))
            changed = v is not None and pc.norm(v) != pc.norm(clean.at[i, column])
            event["key_hits"].append(bool(changed and ne._is_fact("movies", column, v, target["famous"])))
            for col in ne.WATCH["movies"]:
                v = edits.get((j, col))
                changed = v is not None and pc.norm(v) != pc.norm(clean.at[i, col])
                event["cells"].append({"column": col, "changed": bool(changed),
                    "to_fact": bool(changed and ne._is_fact("movies", col, v, target["famous"]))})
    events = list(groups.values())
    for only_known, key in ((False, "key_rates"), (True, "key_rates_known")):
        derived = rates_from_events(events, only_known)
        preserved = ne.key_rates("movies", model, only_known=only_known)
        if derived != preserved or derived != summary[key]:
            raise ValueError(f"Archived near rates/intervals disagree with saved replies: {model}/{key}")
    return {"summary": summary, "events": events}


def _views(modules, frames, read, source):
    pc, mv = modules["probe_clean"], modules["movies_variants"]
    columns, construction, year = {}, {}, {}
    for cond in CONDS:
        dirty, clean = frames[cond]
        errors = {c: int((dirty[c] != clean[c]).sum()) for c in clean.columns}
        repaired = collections.Counter()
        year_preds = {}
        raw = read(source / f"artifacts/raw_outputs/p2/{MODEL}__{cond}__k20__spread.json")
        for chunk in raw["chunks"]:
            local = {}
            for p in pc.parse(chunk["output"]):
                try:
                    r = int(p["row"]) - 1
                except (TypeError, ValueError):
                    continue
                col, v = str(p["column"]), str(p["value"]).strip()
                if 0 <= r < len(chunk["rows"]):
                    i = chunk["rows"][r]
                    if col == "Year":
                        year_preds[i] = v
                    if col in clean.columns and pc.norm(v) != pc.norm(dirty.at[i, col]):
                        local[i, col] = v
            for (i, col), v in local.items():
                if dirty.at[i, col] != clean.at[i, col] and pc.norm(v) == pc.norm(clean.at[i, col]):
                    repaired[col] += 1
        columns[cond] = {c: {"errors": errors[c], "repaired": repaired[c]} for c in clean.columns}
        vals = set()
        for col in pc.IDENTITY["movies"]:
            for v in clean[col]:
                vals.update(("person", n) for n in mv._names(v)) if col in ("Director", "Creator", "Actors") else vals.add((col, v))
        construction[cond] = {"rows": len(clean), "entities": int(clean["Id"].nunique()),
            "errors": sum(errors.values()), "identity_errors": sum(errors[c] for c in pc.IDENTITY["movies"]),
            "values_renamed": len(vals)}
        if cond == "movies_fresh":
            continue
        stats = {"middle year": 0, "first year": 0, "other / unchanged": 0, "ok": 0, "n": 0, "middle_rule_ok": 0}
        for i in range(len(clean)):
            dv, cv = dirty.at[i, "Year"], clean.at[i, "Year"]
            ys = re.findall(r"\d{4}", dv)
            if dv == cv or len(ys) != 3:
                continue
            v = year_preds.get(i)
            stats["n"] += 1
            stats["middle_rule_ok"] += cv == ys[1]
            stats["ok"] += v is not None and pc.norm(v) == pc.norm(cv)
            stats["middle year" if v == ys[1] else "first year" if v == ys[0] else "other / unchanged"] += 1
        year[cond] = stats
    dirty, clean = frames["movies"]
    rt = dirty["Id"] != clean["Id"]
    ids = list(dirty["Id"][rt])
    numbered = sum(bool(re.match(r"\d+-", v)) for v in ids)
    suffix = sum(bool(re.search(r"_\d{4}$", v)) for v in ids)
    people = {}
    for col in ("Director", "Creator"):
        k = collections.Counter({s: 0 for s in ("added", "dropped", "respelled", "emptied")})
        for i in range(len(clean)):
            if dirty.at[i, col] == clean.at[i, col]:
                continue
            others = {mv._fold(x) for other in ("Director", "Creator", "Actors") if other != col for x in mv._names(clean.at[i, other])}
            tpl = mv.people_template(dirty.at[i, col], clean.at[i, col], others)
            if tpl is None:
                k["emptied"] += 1
                continue
            kept = {st[1] for st in tpl if st[0] in ("keep", "alias")}
            k["added"] += sum(st[0] == "other" for st in tpl)
            k["respelled"] += sum(st[0] == "alias" for st in tpl)
            k["dropped"] += len(set(range(len(dict.fromkeys(mv._fold(g) for g in mv._names(clean.at[i, col]))))) - kept)
        people[col] = dict(k)
    duration = [(a, b) for a, b in zip(clean["Duration"], dirty["Duration"]) if a != b]
    rating = [(a, b, r) for a, b, r in zip(clean["RatingValue"], dirty["RatingValue"], rt) if a != b]
    movie_errors = {"total_errors": int((dirty != clean).values.sum()), "rt_rows": int(rt.sum()),
        "errors_by_column": {c: int((dirty[c] != clean[c]).sum()) for c in clean.columns},
        "slug_plain": len(ids) - numbered - suffix, "slug_numbered": numbered, "slug_year": suffix,
        "title_recipe_kinds": len({tuple(op[0] for op in mv.title_recipe(dirty.at[i, "Name"], clean.at[i, "Name"]))
                                  for i in range(len(clean)) if dirty.at[i, "Name"] != clean.at[i, "Name"]}),
        "people": people, "duration_formatted": sum(bool(re.fullmatch(r"\d+ hr\. \d+ min\.", b)) for _, b in duration),
        "duration_empty": sum(b == "" for _, b in duration),
        "rating_score_pair": sum(bool(r and "/10" in b) for a, b, r in rating),
        "rating_empty": sum(bool(r and b == "") for a, b, r in rating),
        "rating_dot0": sum(bool(not r and b == a + ".0") for a, b, r in rating)}
    return {"movies_columns": columns, "construction": construction, "movies_errors": movie_errors, "movies_year": year}


def export(source: Path) -> dict:
    """Export safe projections using frozen saved replies and preserved criteria."""
    source = Path(source).resolve()
    hashes = {}
    def read(path):
        data = path.read_bytes()
        hashes[path.relative_to(source).as_posix()] = hashlib.sha256(data).hexdigest()
        return json.loads(data)
    archives, near, frames = {}, {}, {}
    with _original_modules(source) as modules:
        raw = source / "artifacts/raw_outputs"
        for path in sorted(raw.rglob("*movies*.json")):
            value = read(path)
            family = path.parent.name
            if family == "p2":
                projected = _p2(value, modules, frames)
            elif family == "p1":
                projected = {"summary": value["summary"]}
            elif family == "aligned" and isinstance(value, list):
                cond = path.stem.split("__")[1]
                projected = {"__core_witness__": "aligned_counts_v1", "chunks": modules["aligned"].score(cond, value)}
            elif family == "near" and not path.stem.endswith("__summary"):
                continue
            else:
                projected = _numeric(value)
            archives[path.relative_to(source).as_posix()] = projected
        for path in sorted((raw / "near").glob("*__movies__summary.json")):
            model = path.name.removesuffix("__movies__summary.json")
            near[model] = _near(model, source, modules, read)
            rel = f"artifacts/raw_outputs/near/{model}__movies.json"
            archives[rel] = {"__core_witness__": "near_events_v1", "events": near[model]["events"]}
        for family in ("e4", "e5"):
            path = raw / family / "summary.json"
            archives[path.relative_to(source).as_posix()] = _numeric(read(path))
        views = _views(modules, frames, read, source)
        # Include dependencies read inside original scorers, including screening manifests.
        dependencies = list((source / "code/src").glob("*.py"))
        dependencies += list((source / "data/final").glob("movies*/[cd]*.csv"))
        dependencies += list((source / "data/final/_near/movies").rglob("*.csv"))
        dependencies += list((source / "data/final/_near").glob("screen_plan_movies__*.csv"))
        dependencies += list((source / "data/manifests").glob("*SCREENING*.json"))
        for path in sorted(dependencies):
            hashes[path.relative_to(source).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"archives": archives, "views": views, "near": near,
            "provenance": {"schema": "core_numerical_witness_v1", "source_sha256": hashes,
                "p2": "saved-reply scores independently recomputed with original score_chunk",
                "p1": "saved historical summary projection; no independent raw trial rejudgment",
                "near": "saved-reply entity flags; original fact criteria and full/known bootstrap verified",
                "aligned": "original score converted to counts", "private_manifest_required": True}}
