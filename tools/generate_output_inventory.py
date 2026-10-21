#!/usr/bin/env python3
"""Generate the complete archived-output and reference-product inventory."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def kind_for(path: Path) -> str:
    rel = path.relative_to(ROOT)
    if rel.parts[:2] == ("artifacts", "raw_outputs"):
        return rel.parts[2]
    if rel.parts[:2] == ("results", "derived"):
        return "summary"
    if rel.parts[:2] == ("results", "tables"):
        return "table"
    if rel.parts[:2] == ("results", "figures"):
        return "figure"
    raise ValueError(f"unclassified artifact: {rel}")


def entries() -> list[dict[str, str]]:
    files = []
    for base in (ROOT / "artifacts/raw_outputs", ROOT / "results"):
        for path in base.rglob("*"):
            if path.is_file() and path.name != "output-inventory.json":
                files.append(path)
    return [
        {
            "relative_path": path.relative_to(ROOT).as_posix(),
            "kind": kind_for(path),
            "paper_consumer": "paper",
        }
        for path in sorted(files)
    ]


def main() -> None:
    target = ROOT / "results/derived/output-inventory.json"
    target.write_text(json.dumps(entries(), indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {target} ({len(entries())} entries)")


if __name__ == "__main__":
    main()
