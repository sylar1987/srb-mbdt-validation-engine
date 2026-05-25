"""Tests für die DSL-basierte Prerequisite-Auswertung (Phase 2 Migration)."""

import pandas as pd

from app.validation.prerequisite_evaluator import (
    evaluate,
    last_diagnostics,
)


def _df():
    return pd.DataFrame(
        {
            "c0250": ["Structured", "Non-Structured/Vanilla", None, "Other non-standard terms"],
            "c0240": ["A", "ZCB issued at discount", "B", "A"],
            "c0040": ["ISIN", "CUSIP", "ISIN", None],
        }
    )


def test_evaluate_empty_prerequisite_always_true():
    assert evaluate(_df(), 0, "", {}) is True


def test_evaluate_simple_equality_dsl_path():
    df = _df()
    assert evaluate(df, 0, 'Rule applicable only if c0040 = "ISIN"', {}) is True
    assert evaluate(df, 1, 'Rule applicable only if c0040 = "ISIN"', {}) is False


def test_evaluate_or_membership():
    df = _df()
    text = 'Rule applicable if c0250 = ("Non-Structured/Vanilla" OR "Other non-standard terms")'
    assert evaluate(df, 1, text, {}) is True
    assert evaluate(df, 3, text, {}) is True
    assert evaluate(df, 0, text, {}) is False


def test_evaluate_and_conjunction():
    df = _df()
    text = (
        'Rule applicable if c0250 = ("Non-Structured/Vanilla" OR "Other non-standard terms") '
        'AND c0240 != "ZCB issued at discount"'
    )
    assert evaluate(df, 3, text, {}) is True  # Other non-standard terms, c0240=A
    assert evaluate(df, 1, text, {}) is False  # Non-Structured/Vanilla, ZCB issued at discount


def test_evaluate_falls_back_to_legacy_for_unsupported():
    df = _df()
    # Phase-1-Heuristik fängt diesen freien Text ein und liefert True
    # (konservativ, keine stille Unterdrückung).
    result = evaluate(df, 0, "rule applicable for some narrative reason", {})
    assert result is True
    diags = last_diagnostics()
    assert any("DSL" in d.code.value for d in diags)


def test_evaluate_legacy_heuristic_structured_only():
    df = _df()
    text = 'Rule applicable if c0250 = ("Structured" OR "Only structured coupon")'
    # DSL-Pfad
    assert evaluate(df, 0, text, {}) is True
    assert evaluate(df, 1, text, {}) is False  # Non-Structured/Vanilla
