"""Tests für Hilfsfunktionen."""

from __future__ import annotations

import datetime as dt

from app.utils import (
    DATE_RE,
    ISIN_RE,
    LEI_RE,
    is_missing,
    safe_float,
    parse_date,
    ISO_4217_CURRENCIES,
)


def test_is_missing():
    assert is_missing("")
    assert is_missing("N/A")
    assert is_missing("nan")
    assert is_missing(None)
    assert not is_missing("Value")
    assert not is_missing("0")


def test_safe_float():
    assert safe_float("1,5") == 1.5
    assert safe_float("3.14") == 3.14
    assert safe_float("abc") is None
    assert safe_float("") is None


def test_parse_date_variants():
    assert parse_date("2024-12-31") == dt.date(2024, 12, 31)
    assert parse_date("31.12.2024") == dt.date(2024, 12, 31)
    assert parse_date("31/12/2024") == dt.date(2024, 12, 31)
    assert parse_date("20241231") == dt.date(2024, 12, 31)
    assert parse_date("not a date") is None


def test_regex():
    assert DATE_RE.match("2024-12-31")
    assert ISIN_RE.match("DE000A1EWWW0")
    assert LEI_RE.match("529900T8BM49AURSDO55")
    assert "EUR" in ISO_4217_CURRENCIES
