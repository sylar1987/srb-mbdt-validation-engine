"""Tests für den assertion-basierten Expression-Validator (Phase 2)."""

import pandas as pd

from app.config.catalog_loader import Catalog
from app.models import InputBatch, RuleDefinitionV2
from app.validation.context import ValidationContext
from app.validation.expression_validator import validate_v2


def _ctx_with(template_id: str, df: pd.DataFrame) -> ValidationContext:
    batch = InputBatch(templates={template_id: df}, entity_name="TEST", reference_date="2025-12-31")
    catalog = Catalog(rules=[], raw_rules=[], codelists={}, field_codelist_map={})
    return ValidationContext(batch=batch, catalog=catalog)


def test_validate_row_mandatory_field_via_assertion():
    df = pd.DataFrame({"c0040": ["ISIN", "ISIN"], "c0070": ["12345", None]})
    ctx = _ctx_with("B02.00", df)
    rule = RuleDefinitionV2(
        rule_id="R1",
        scope="row",
        target_template="B02.00",
        condition='c0040 = "ISIN"',
        assertion='is_not_null(c0070)',
        severity="ERROR",
        message="c0070 muss berichtet sein, wenn c0040=ISIN",
        metadata={"rule_level": "L1", "rule_type": "MANDATORY_FIELD", "field_code": "c0070"},
    )
    issues = validate_v2(ctx, rule)
    assert len(issues) == 1
    assert issues[0].rule_id == "R1"
    assert issues[0].row == 3  # zweite Zeile (0-basiert + 2)


def test_validate_row_condition_filters_out():
    df = pd.DataFrame({"c0040": ["CUSIP"], "c0070": [None]})
    ctx = _ctx_with("B02.00", df)
    rule = RuleDefinitionV2(
        rule_id="R2",
        scope="row",
        target_template="B02.00",
        condition='c0040 = "ISIN"',
        assertion='is_not_null(c0070)',
    )
    assert validate_v2(ctx, rule) == []


def test_validate_row_no_assertion_yields_no_issues():
    df = pd.DataFrame({"c0040": ["ISIN"]})
    ctx = _ctx_with("B02.00", df)
    rule = RuleDefinitionV2(rule_id="R3", target_template="B02.00", condition='c0040 = "ISIN"')
    assert validate_v2(ctx, rule) == []


def test_validate_row_missing_template_returns_empty():
    df = pd.DataFrame({"c0040": ["ISIN"]})
    ctx = _ctx_with("B02.00", df)
    rule = RuleDefinitionV2(
        rule_id="R4",
        target_template="B99.99",
        assertion='is_not_null(c0040)',
    )
    assert validate_v2(ctx, rule) == []
