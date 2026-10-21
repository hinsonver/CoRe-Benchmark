#!/usr/bin/env python3
"""Offline structural and safety checks for the CoRe artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


IGNORED_DIRS = {".git", "build", "__pycache__", "tests", "tools", ".venv"}
PRIVATE_PATHS = ("/Users/oki", "/data/YJR")


def _release_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        yield path, rel


def find_forbidden_files(root: Path) -> list[str]:
    findings = []
    for path, rel in _release_files(root):
        name = path.name
        if name == ".env" or name.startswith(".env.") or name == ".DS_Store":
            findings.append(rel.as_posix())
        elif name.endswith((".log", ".pid")) or (name.startswith("cache") and name.endswith(".jsonl")):
            findings.append(rel.as_posix())
    return sorted(findings)


def find_private_paths(root: Path) -> list[str]:
    findings = []
    for path, rel in _release_files(root):
        if path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".gif"}:
            continue
        text = path.read_text(errors="ignore")
        for needle in PRIVATE_PATHS:
            if needle in text:
                findings.append(f"{rel.as_posix()}: {needle}")
    return sorted(findings)


def validate_retained_exception(path: Path) -> list[str]:
    rows = json.loads(path.read_text())
    failed = [row for row in rows if row.get("ok") is False]
    expected_table = "hospital_surrogatewords"
    expected_check = "identity columns: characters replaced per error cell (1 / 2 / 3+) within 8 points of the original"
    if len(failed) != 1:
        return [f"expected exactly one retained validation failure, found {len(failed)}"]
    row = failed[0]
    issues = []
    if row.get("table") != expected_table:
        issues.append(f"unexpected failed table: {row.get('table')}")
    if row.get("check") != expected_check:
        issues.append(f"unexpected failed check: {row.get('check')}")
    return issues


def validate_json(root: Path) -> list[str]:
    issues = []
    for path, rel in _release_files(root):
        if path.suffix != ".json":
            continue
        try:
            json.loads(path.read_text())
        except Exception as exc:
            issues.append(f"{rel.as_posix()}: {type(exc).__name__}")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true", help="enforce public-release gates")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    checks = {
        "forbidden files": find_forbidden_files(root),
        "private absolute paths": find_private_paths(root),
        "JSON parse": validate_json(root),
        "retained validation exception": validate_retained_exception(root / "results/derived/validate_tables.json"),
    }
    failed = False
    for name, issues in checks.items():
        if issues:
            failed = True
            print(f"FAIL {name}: " + "; ".join(issues))
        else:
            print(f"PASS {name}")
    blockers = []
    if not (root / "CITATION.cff").is_file():
        blockers.append("CITATION.cff awaits the final author list")
    try:
        sys.path.insert(0, str(root))
        from tools.core import verify
        blockers.extend(verify(root, release=args.release)["release_gates"])
    except Exception as exc:
        blockers.append("statistical-core evidence binding: " + str(exc))
    if blockers:
        label = "FAIL" if args.release else "STAGING"
        print(f"{label} release gates: " + "; ".join(blockers))
        failed = failed or args.release
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

