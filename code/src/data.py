"""Load the frozen cleaning benchmarks as aligned string frames."""
import os
from pathlib import Path

import pandas as pd

ROOT = Path(os.environ.get("CORE_ARTIFACT_ROOT", Path(__file__).resolve().parents[2])).resolve()
RAW = ROOT / "data" / "final"
ARCHIVE = ROOT / "artifacts" / "raw_outputs"
BUILD = Path(os.environ.get("CORE_BUILD_DIR", ROOT / "build")).resolve()
DATASETS = ["hospital", "flights", "beers", "rayyan", "movies_1", "tax"]


def load(name: str, max_rows: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (dirty, clean) with identical shape and clean-side column names.

    All cells are strings; empty cells stay "" (no NaN), so cell equality is exact.
    """
    if name.startswith("movies") or name.startswith("_near/movies"):
        from .core_runtime import private_file
        movie_clean = private_file("data/final/" + name + "/clean.csv")
        movie_dirty = private_file("data/final/" + name + "/dirty.csv")
        clean = pd.read_csv(movie_clean, dtype=str, keep_default_na=False)
        dirty = pd.read_csv(movie_dirty, dtype=str, keep_default_na=False)
        dirty.columns = clean.columns
        return dirty.reset_index(drop=True), clean.reset_index(drop=True)
    clean = pd.read_csv(RAW / name / "clean.csv", dtype=str, keep_default_na=False)
    dirty = pd.read_csv(RAW / name / "dirty.csv", dtype=str, keep_default_na=False)
    if clean.shape != dirty.shape:
        raise ValueError(f"{name}: shape mismatch {clean.shape} vs {dirty.shape}")
    # Dirty headers differ in some datasets (e.g. hospital, beers); align by position.
    dirty.columns = clean.columns
    if max_rows is not None:
        clean, dirty = clean.iloc[:max_rows], dirty.iloc[:max_rows]
    return dirty.reset_index(drop=True), clean.reset_index(drop=True)


def counter_columns(df: pd.DataFrame) -> list[str]:
    """Columns that are row counters (each value = previous + 1), e.g. hospital's `index`
    or flights' `tuple_id`. Their next value is trivially predictable, so probes must not
    count them as memorization evidence."""
    cols = []
    for col in df.columns:
        vals = pd.to_numeric(df[col], errors="coerce")
        if vals.notna().all() and len(vals) > 1 and (vals.diff().iloc[1:] == 1).all():
            cols.append(col)
    return cols


def error_mask(dirty: pd.DataFrame, clean: pd.DataFrame) -> pd.DataFrame:
    return dirty.ne(clean)


def to_csv_block(df: pd.DataFrame, header: bool = True) -> str:
    return df.to_csv(index=False, header=header).rstrip("\n")
