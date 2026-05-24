"""Tests für Normalisierung."""

from __future__ import annotations

import pandas as pd

from app.normalization import (
    normalize_col_names,
    find_header_row,
    extract_headers,
    replace_blank_with_na,
)
from app.normalization.headers import find_column


def test_normalize_col_names_4digit():
    assert normalize_col_names(["0010", "0020"]) == ["c0010", "c0020"]


def test_normalize_col_names_dedup():
    out = normalize_col_names(["foo", "foo", "foo"])
    assert out == ["foo", "foo_1", "foo_2"]


def test_normalize_col_names_short_digits():
    assert normalize_col_names(["10", "20"]) == ["c0010", "c0020"]


def test_find_header_row_int_codes():
    rows = [
        ("Some title", None, None),
        ("Label1", "Label2", "Label3"),
        (10, 20, 30),
        ("a", "b", "c"),
    ]
    assert find_header_row(rows) == 2


def test_extract_headers():
    rows = [
        ("Title", None, None),
        ("Label A", "Label B", "Label C"),
        (10, 20, 30),
    ]
    headers = extract_headers(rows, 2)
    assert headers == ["c0010", "c0020", "c0030"]


def test_replace_blank_with_na():
    df = pd.DataFrame({"a": ["", "X", "None"]})
    out = replace_blank_with_na(df)
    assert pd.isna(out["a"].iloc[0])
    assert out["a"].iloc[1] == "X"


def test_find_column_flexible():
    df = pd.DataFrame({"c0040": ["x"]})
    assert find_column(df, "c0040") == "c0040"
    assert find_column(df, "0040") == "c0040"
    assert find_column(df, "40") == "c0040"
    assert find_column(df, "c9999") is None
