"""Lectura de archivos tabulares por extensión."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SUPPORTED = (".csv", ".tsv", ".txt", ".parquet", ".pq", ".json", ".jsonl", ".ndjson", ".xlsx")


def read_table(
    path: str | Path, *, sep: str | None = None, parse_dates: list[str] | None = None, encoding: str = "utf-8"
) -> pd.DataFrame:
    """Lee CSV/TSV, Parquet, JSON/JSON Lines o Excel según la extensión.

    Para CSV, si ``sep`` es ``None`` se detecta automáticamente (coma, punto y coma, tab, |).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo: {p}")
    ext = p.suffix.lower()
    if ext in (".csv", ".tsv", ".txt"):
        if sep is None and ext == ".tsv":
            sep = "\t"
        df = pd.read_csv(
            p, sep=sep, engine="python" if sep is None else "c", encoding=encoding, parse_dates=parse_dates
        )
    elif ext in (".parquet", ".pq"):
        df = pd.read_parquet(p)
    elif ext in (".jsonl", ".ndjson"):
        df = pd.read_json(p, lines=True)
    elif ext == ".json":
        df = pd.read_json(p)
    elif ext == ".xlsx":
        df = pd.read_excel(p)
    else:
        raise ValueError(f"Extensión no soportada '{ext}'. Soportadas: {', '.join(SUPPORTED)}")
    if parse_dates and ext not in (".csv", ".tsv", ".txt"):
        for c in parse_dates:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df
