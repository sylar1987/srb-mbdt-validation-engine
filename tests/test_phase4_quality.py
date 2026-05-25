"""Phase-4-Tests: Quality-Layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import (
    CodelistDefinition,
    DataPointDefinition,
    MetadataPackage,
    RuleDefinitionV2,
    TemplateDefinition,
)
from app.quality import (
    ConformanceLevel,
    ExportConformanceChecker,
    MetadataAcceptanceChecker,
    RegressionCase,
    RegressionRunResult,
    RegressionSuite,
    generate_rule_test_requirements,
)


# --- ExportConformanceChecker ----------------------------------------------


def _write_metadata(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_conformance_checker_missing_directory_emits_error() -> None:
    checker = ExportConformanceChecker()
    report = checker.check("/nonexistent/path/never")
    assert report.has_errors()
    assert any(f.code == "CONF000" for f in report.findings)


def test_conformance_checker_minimum_mvp_payload_passes_with_warnings(tmp_path) -> None:
    (tmp_path / "facts.csv").write_text("fact_id,value\n", encoding="utf-8")
    _write_metadata(
        tmp_path / "metadata.json",
        {
            "framework_version": "4.2",
            "package_id": "PKG-1",
            "metadata_version": "hash",
            "fact_count": 0,
        },
    )
    (tmp_path / "parameters.csv").write_text("name,value\n", encoding="utf-8")

    checker = ExportConformanceChecker()
    report = checker.check(str(tmp_path))
    assert not report.has_errors()
    codes = {f.code for f in report.findings}
    assert "CONF030" in codes  # filing_indicators warning
    assert "CONF031" in codes  # taxonomy_reference warning
    assert "CONF040" in codes  # report.json info


def test_conformance_checker_full_oim_extras_no_warnings(tmp_path) -> None:
    (tmp_path / "facts.csv").write_text("fact_id\n", encoding="utf-8")
    _write_metadata(
        tmp_path / "metadata.json",
        {
            "framework_version": "4.2",
            "package_id": "PKG-1",
            "metadata_version": "hash",
            "filing_indicators": ["FI_B02"],
            "taxonomy_reference": "https://example.org/taxonomy/4.2",
        },
    )
    (tmp_path / "parameters.csv").write_text("name,value\n", encoding="utf-8")
    (tmp_path / "report.json").write_text("{}", encoding="utf-8")

    checker = ExportConformanceChecker()
    report = checker.check(str(tmp_path))
    assert not report.has_errors()
    assert report.warning_count() == 0
    assert "facts.csv" in report.checked_files


def test_conformance_checker_reports_missing_metadata_fields(tmp_path) -> None:
    (tmp_path / "facts.csv").write_text("", encoding="utf-8")
    _write_metadata(tmp_path / "metadata.json", {"framework_version": ""})
    checker = ExportConformanceChecker()
    report = checker.check(str(tmp_path))
    error_codes = {f.code for f in report.findings if f.level == ConformanceLevel.ERROR}
    assert "CONF020" in error_codes


def test_conformance_checker_handles_corrupt_metadata(tmp_path) -> None:
    (tmp_path / "facts.csv").write_text("", encoding="utf-8")
    (tmp_path / "metadata.json").write_text("not-json", encoding="utf-8")
    checker = ExportConformanceChecker()
    report = checker.check(str(tmp_path))
    assert any(f.code == "CONF010" for f in report.findings)


# --- MetadataAcceptanceChecker ---------------------------------------------


def _package(**overrides) -> MetadataPackage:
    base = dict(
        package_id="PKG-1",
        framework_version="4.2",
        datapoints=[
            DataPointDefinition(datapoint_id="dp-1", template_id="B02.00", field_code="c0010"),
        ],
        templates=[
            TemplateDefinition(template_id="B02.00", datapoint_ids=["dp-1"]),
        ],
        codelists=[CodelistDefinition(codelist_id="CL-1", values=["A"])],
        rules=[],
    )
    base.update(overrides)
    return MetadataPackage(**base)


def test_metadata_acceptance_warns_when_no_rules() -> None:
    package = _package()
    checker = MetadataAcceptanceChecker()
    report = checker.check(package)
    assert not report.has_errors()
    assert any(f.code == "ACCEPT004" for f in report.findings)


def test_metadata_acceptance_errors_on_missing_framework_version() -> None:
    package = _package(framework_version="")
    checker = MetadataAcceptanceChecker()
    report = checker.check(package)
    assert report.has_errors()
    assert any(f.code == "ACCEPT001" for f in report.findings)


def test_metadata_acceptance_flags_unknown_codelist_reference() -> None:
    package = _package(
        datapoints=[
            DataPointDefinition(
                datapoint_id="dp-1",
                template_id="B02.00",
                field_code="c0010",
                codelist_id="CL-MISSING",
            )
        ]
    )
    checker = MetadataAcceptanceChecker()
    report = checker.check(package)
    assert report.has_errors()
    assert any(f.code == "ACCEPT006" for f in report.findings)


def test_metadata_acceptance_flags_untranslatable_rules() -> None:
    untranslatable_rule = RuleDefinitionV2(
        rule_id="R1",
        scope="row",
        target_template="B02.00",
        condition="",
        assertion="",
        metadata={"translatable": False},
    )
    package = _package(rules=[untranslatable_rule])
    checker = MetadataAcceptanceChecker()
    report = checker.check(package)
    assert any(f.code == "ACCEPT005" for f in report.findings)


# --- RuleTestGenerator -----------------------------------------------------


def test_rule_test_generator_emits_pos_neg_for_each_rule() -> None:
    rule = RuleDefinitionV2(
        rule_id="R1",
        scope="row",
        target_template="B02.00",
        condition='c0010 = "X"',
        assertion="is_not_null(c0020)",
    )
    reqs = generate_rule_test_requirements([rule])
    types = {(r.rule_id, r.test_type, r.metadata.get("variant")) for r in reqs}
    assert ("R1", "positive", None) in types
    assert ("R1", "negative", None) in types
    assert ("R1", "positive", "condition_false") in types


def test_rule_test_generator_marks_untranslatable_as_manual() -> None:
    rule = RuleDefinitionV2(
        rule_id="R-UT",
        scope="row",
        condition="",
        assertion="",
        metadata={"translatable": False},
    )
    reqs = generate_rule_test_requirements([rule])
    assert len(reqs) == 1
    assert reqs[0].test_type == "manual"
    assert reqs[0].metadata.get("reason") == "untranslatable"


# --- RegressionSuite -------------------------------------------------------


def test_regression_suite_summary_tracks_executions() -> None:
    suite = RegressionSuite("phase4-pilot")
    suite.add_case(RegressionCase(case_id="c1", description="pilot baseline"))
    suite.add_case(RegressionCase(case_id="c2", description="negative path"))

    suite.record_result(RegressionRunResult(case_id="c1", status="passed"))
    suite.record_result(
        RegressionRunResult(case_id="c2", status="failed", actual_error_count=2)
    )

    summary = suite.summary()
    assert summary["case_count"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["missing_executions"] == []


def test_regression_suite_rejects_unknown_case_or_status() -> None:
    suite = RegressionSuite("p4")
    with pytest.raises(KeyError):
        suite.record_result(RegressionRunResult(case_id="nope", status="passed"))

    suite.add_case(RegressionCase(case_id="c1", description="x"))
    with pytest.raises(ValueError):
        suite.record_result(RegressionRunResult(case_id="c1", status="not-a-status"))
