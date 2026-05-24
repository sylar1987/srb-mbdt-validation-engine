"""Tests für ``RuleDefinitionV2`` und den Mapper aus ``RuleDefinition``."""

import pytest

from app.models import RuleDefinition, RuleDefinitionV2, map_legacy_rule
from app.models.rule_v2 import translate_legacy_prerequisite


def test_rule_definition_v2_minimum_required():
    rule = RuleDefinitionV2(rule_id="R1")
    assert rule.scope == "row"
    assert rule.severity == "ERROR"


def test_rule_definition_v2_invalid_scope():
    with pytest.raises(ValueError):
        RuleDefinitionV2(rule_id="R1", scope="bogus")


def test_rule_definition_v2_roundtrip_dict():
    rule = RuleDefinitionV2(
        rule_id="R1",
        scope="cross",
        target_template="B02.00",
        condition='c0040 = "ISIN"',
        assertion="is_not_null(c0050)",
        severity="WARN",
        message="Hinweis",
        source="dpm:test",
        metadata={"foo": "bar"},
    )
    data = rule.to_dict()
    assert RuleDefinitionV2.from_dict(data) == rule


def test_translate_legacy_prerequisite_empty():
    assert translate_legacy_prerequisite("") == ""


@pytest.mark.parametrize(
    "text,expected",
    [
        ('Rule applicable only if c0040 = "ISIN"', 'c0040 = "ISIN"'),
        ('Rule applicable if c0250 = ("Structured" OR "Only structured coupon")',
         'c0250 in ("Structured", "Only structured coupon")'),
        ('Rule applicable only if c0250 != ("Structured" OR "Only structured coupon")',
         'c0250 not in ("Structured", "Only structured coupon")'),
        ('Rule applicable if c0250 = ("Non-Structured/Vanilla" OR "Other non-standard terms") '
         'AND c0240 != "ZCB issued at discount"',
         'c0250 in ("Non-Structured/Vanilla", "Other non-standard terms") '
         'and c0240 != "ZCB issued at discount"'),
        ('Rule applicable only if c0140 != "Cash account/saving account".',
         'c0140 != "Cash account/saving account"'),
    ],
)
def test_translate_legacy_prerequisite_known_shapes(text, expected):
    assert translate_legacy_prerequisite(text) == expected


def test_translate_legacy_prerequisite_unsupported():
    """Frei-formulierte Bedingungen liefern None."""
    assert translate_legacy_prerequisite("Rule applicable if reasonable and structured") is None


def test_map_legacy_rule_mandatory_field():
    legacy = RuleDefinition.from_dict({
        "rule_id": "L1_C0070",
        "rule_level": "L1",
        "rule_type": "MANDATORY_FIELD",
        "template": "B02.00",
        "field_code": "c0070",
        "field_label": "Foo",
        "severity": "ERROR",
        "prerequisite": 'Rule applicable only if c0040 = "ISIN"',
    })
    v2 = map_legacy_rule(legacy)
    assert v2 is not None
    assert v2.rule_id == "L1_C0070"
    assert v2.scope == "row"
    assert v2.target_template == "B02.00"
    assert v2.condition == 'c0040 = "ISIN"'
    assert v2.assertion == "is_not_null(c0070)"
    assert v2.source == "legacy:rule_catalog.json"
    assert v2.metadata["rule_level"] == "L1"
    assert v2.metadata["rule_type"] == "MANDATORY_FIELD"


def test_map_legacy_rule_unsupported_prereq_returns_none():
    legacy = RuleDefinition.from_dict({
        "rule_id": "X1",
        "rule_level": "L1",
        "rule_type": "MANDATORY_FIELD",
        "template": "B02.00",
        "field_code": "c0070",
        "prerequisite": "Rule applicable if some natural language constraint",
    })
    assert map_legacy_rule(legacy) is None


def test_map_legacy_rule_cross_level():
    legacy = RuleDefinition.from_dict({
        "rule_id": "C1",
        "rule_level": "CROSS",
        "rule_type": "CROSS_TEMPLATE",
        "template": "B02.00",
        "field_code": "c0040",
        "prerequisite": "",
    })
    v2 = map_legacy_rule(legacy)
    assert v2 is not None
    assert v2.scope == "cross"
    assert v2.condition == ""
