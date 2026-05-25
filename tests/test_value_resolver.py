"""Tests für DPM Value-Alias-Auflösung."""

from __future__ import annotations

import pandas as pd

from app.normalization.value_resolver import (
    canonicalize_for_compare,
    resolve_value,
)
from app.models import RuleDefinition
from app.validation import codelist_validator, prerequisite_evaluator
from tests.test_native_validators import _ctx_with


ALLOWED = ["SCT", "DCT", "Resolution Entity", "Other"]


# ── value_resolver unit ────────────────────────────────────────────────────


def test_resolve_exact_code():
    r = resolve_value("SCT", ALLOWED)
    assert r.matched and r.value == "SCT"


def test_resolve_code_dash_caption():
    r = resolve_value("SCT - Secured collateralized liabilities", ALLOWED)
    assert r.matched and r.value == "SCT"


def test_resolve_code_colon_caption():
    r = resolve_value("SCT: Secured collateralized", ALLOWED)
    assert r.matched and r.value == "SCT"


def test_resolve_code_paren_caption():
    r = resolve_value("SCT (Secured collateralized)", ALLOWED)
    assert r.matched and r.value == "SCT"


def test_resolve_code_pipe_caption():
    r = resolve_value("SCT | Secured collateralized", ALLOWED)
    assert r.matched and r.value == "SCT"


def test_resolve_multiword_code():
    r = resolve_value("Resolution Entity", ALLOWED)
    assert r.matched and r.value == "Resolution Entity"


def test_resolve_unknown():
    r = resolve_value("XYZ - Bogus", ALLOWED)
    assert not r.matched
    assert "kein Treffer" in r.reason or r.reason


def test_resolve_caption_only_unique():
    caption_map = {"Secured collateralized liabilities": "SCT"}
    r = resolve_value("Secured collateralized liabilities", ALLOWED, caption_map)
    assert r.matched and r.value == "SCT"


def test_resolve_caption_only_ambiguous():
    caption_map = {"Secured": "SCT", "secured": "DCT"}
    r = resolve_value("Secured", ALLOWED, caption_map)
    assert not r.matched
    assert r.ambiguous


def test_resolve_empty_input():
    r = resolve_value("", ALLOWED)
    assert not r.matched


# ── canonicalize_for_compare ───────────────────────────────────────────────


def test_canonical_with_allowed_reduces():
    assert canonicalize_for_compare("SCT - Caption", ALLOWED) == "SCT"


def test_canonical_with_allowed_keeps_unknown():
    assert canonicalize_for_compare("XYZ - Caption", ALLOWED) == "XYZ - Caption"


def test_canonical_without_allowed_short_code():
    assert canonicalize_for_compare("SCT - Caption") == "SCT"


def test_canonical_preserves_iso_date():
    # ISO-Datum darf nicht zerteilt werden ("2024" + "12-31")
    assert canonicalize_for_compare("2024-12-31") == "2024-12-31"


def test_canonical_preserves_lei():
    lei = "529900XXXX0000000001"
    assert canonicalize_for_compare(lei) == lei


def test_canonical_preserves_numeric():
    assert canonicalize_for_compare("1000.50") == "1000.50"


# ── codelist_validator Integration ─────────────────────────────────────────


def _codelist_rule() -> RuleDefinition:
    return RuleDefinition(
        rule_id="T_CL_ALIAS",
        rule_level="CL",
        rule_type="CODELIST_CHECK",
        template="B02.00",
        field_code="c0140",
        field_label="Nature of the liability",
        codelist_name="Nature of the liability",
    )


def test_codelist_accepts_code_alone():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0140": ["Loan"]})})
    assert codelist_validator.validate(ctx, _codelist_rule()) == []


def test_codelist_accepts_code_dash_caption():
    ctx = _ctx_with(
        {"B02.00": pd.DataFrame({"c0140": ["Loan - Klassisches Darlehen"]})}
    )
    assert codelist_validator.validate(ctx, _codelist_rule()) == []


def test_codelist_accepts_code_colon_caption():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0140": ["Loan: Darlehen"]})})
    assert codelist_validator.validate(ctx, _codelist_rule()) == []


def test_codelist_accepts_code_paren_caption():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0140": ["Loan (Darlehen)"]})})
    assert codelist_validator.validate(ctx, _codelist_rule()) == []


def test_codelist_accepts_code_pipe_caption():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0140": ["Loan | Darlehen"]})})
    assert codelist_validator.validate(ctx, _codelist_rule()) == []


def test_codelist_still_rejects_unknown_code():
    ctx = _ctx_with(
        {"B02.00": pd.DataFrame({"c0140": ["Bogus - irgendwas"]})}
    )
    issues = codelist_validator.validate(ctx, _codelist_rule())
    assert len(issues) == 1


# ── prerequisite_evaluator: CODE - Caption == CODE ─────────────────────────


def test_prerequisite_code_vs_code_caption_equal():
    # Regelwert technisch, Input mit Caption
    df = pd.DataFrame({"c0140": ["SCT - Secured collateralized liabilities"]})
    assert prerequisite_evaluator.evaluate(df, 0, "c0140='SCT'", {}) is True


def test_prerequisite_code_caption_vs_code_equal():
    # Regelwert mit Caption, Input technisch
    df = pd.DataFrame({"c0140": ["SCT"]})
    assert (
        prerequisite_evaluator.evaluate(
            df, 0, "c0140='SCT - Secured collateralized liabilities'", {}
        )
        is True
    )


def test_prerequisite_does_not_match_unrelated():
    df = pd.DataFrame({"c0140": ["DCT"]})
    assert prerequisite_evaluator.evaluate(df, 0, "c0140='SCT'", {}) is False
