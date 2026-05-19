"""Tests für CSV-Loader."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.io import load_csv_dir, load_single_csv


def _write_csv(path: Path, header: list, rows: list):
    with open(path, "w", encoding="utf-8-sig") as fh:
        fh.write(";".join(header) + "\n")
        for r in rows:
            fh.write(";".join(r) + "\n")


def test_load_single_csv(tmp_path: Path):
    f = tmp_path / "B02.00_TypeA.csv"
    _write_csv(f, ["0010", "0020"], [["1", "X"], ["2", "Y"]])
    batch = load_single_csv(f, "B02.00")
    assert "B02.00" in batch
    df = batch.get("B02.00")
    assert list(df.columns) == ["c0010", "c0020"]
    assert len(df) == 2


def test_load_csv_dir_combines_variants(tmp_path: Path):
    a = tmp_path / "B02.00_TypeA.csv"
    b = tmp_path / "B02.00_TypeB.csv"
    _write_csv(a, ["0010", "0020"], [["1", "X"]])
    _write_csv(b, ["0010", "0020"], [["2", "Y"]])
    batch = load_csv_dir(tmp_path)
    assert "B02.00_TypeA" in batch
    assert "B02.00_TypeB" in batch
    assert batch.source_type == "csv_dir"


def test_load_csv_dir_dtype_str(tmp_path: Path):
    f = tmp_path / "B02.00_TypeA.csv"
    _write_csv(f, ["0010", "0020"], [["123", "001"]])
    batch = load_csv_dir(tmp_path)
    df = batch.get("B02.00_TypeA")
    assert df["c0010"].iloc[0] == "123"
    assert df["c0020"].iloc[0] == "001"  # führende Null erhalten


def test_csv_blank_to_na(tmp_path: Path):
    f = tmp_path / "B02.00_TypeA.csv"
    _write_csv(f, ["0010", "0020"], [["", "X"]])
    batch = load_csv_dir(tmp_path)
    df = batch.get("B02.00_TypeA")
    assert pd.isna(df["c0010"].iloc[0])
