"""Tests für die Dataclasses."""

from __future__ import annotations

import pandas as pd

from app.models import (
    InputBatch,
    RuleDefinition,
    TemplateData,
    ValidationIssue,
    ValidationSummary,
)


def test_template_data_basic():
    df = pd.DataFrame({"c0010": ["1"], "c0020": ["A"]})
    td = TemplateData(template_id="B02.00", key="B02.00", df=df, source_name="x.csv")
    assert td.row_count == 1
    assert "c0010" in td.to_debug_dict()["columns"]


def test_input_batch_add():
    batch = InputBatch(source_type="csv_dir", source_path="/tmp")
    df = pd.DataFrame({"c0010": ["1"]})
    batch.add(TemplateData(template_id="B99.00", key="B99.00", df=df))
    assert "B99.00" in batch
    assert batch.get("B99.00") is df


def test_rule_definition_from_dict_and_back():
    raw = {
        "rule_id": "v_L1_0001", "rule_level": "L1", "rule_type": "MANDATORY_FIELD",
        "template": "B02.00", "field_code": "c0010", "severity": "ERROR",
        "de_only": False,
    }
    rd = RuleDefinition.from_dict(raw)
    assert rd.rule_id == "v_L1_0001"
    assert rd.rule_level == "L1"
    assert rd.to_legacy_dict() == raw


def test_validation_issue_roundtrip():
    src = {
        "rule_id": "v_CL_0001", "rule_level": "CL", "rule_type": "CODELIST_CHECK",
        "template": "B02.00", "row": 5, "field_code": "c0040",
        "field_label": "Type", "severity": "ERROR",
        "value": "FOO", "message": "Ungültig", "explanation": "",
        "dpm_reference": "",
    }
    iss = ValidationIssue.from_dict(src)
    out = iss.to_dict()
    assert out["rule_id"] == "v_CL_0001"
    assert out["row"] == 5
    assert out["value"] == "FOO"


def test_validation_summary_from_issues():
    issues = [
        ValidationIssue(rule_id="r1", rule_level="L1", rule_type="MANDATORY_FIELD",
                        template="B02.00", severity="ERROR"),
        ValidationIssue(rule_id="r2", rule_level="L1", rule_type="MANDATORY_FIELD",
                        template="B02.00", severity="WARNING"),
        ValidationIssue(rule_id="r3", rule_level="CL", rule_type="CODELIST_CHECK",
                        template="B99.00", severity="ERROR"),
    ]
    summ = ValidationSummary.from_issues(issues, ["B02.00", "B99.00"])
    assert summ.total == 3
    assert summ.errors == 2
    assert summ.warnings == 1
    assert summ.by_template["B02.00"] == 2
    assert summ.by_rule_level["L1"] == 2
