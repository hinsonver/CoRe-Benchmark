#!/usr/bin/env python3
"""Generate a deterministic SHA-256 manifest for the artifact."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys


EXCLUDED_DIRS = {".git", "build", "__pycache__", ".venv"}
EXCLUDED_FILES = {"MANIFEST.sha256", ".DS_Store"}


def manifest_lines(root: Path) -> list[str]:
    paths = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in rel.parts) or path.name in EXCLUDED_FILES:
            continue
        paths.append(path)
    lines = []
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root).as_posix()}")
    return lines


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    target = root / "MANIFEST.sha256"
    target.write_text("\n".join(manifest_lines(root)) + "\n")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

