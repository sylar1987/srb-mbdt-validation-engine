"""Phase 3 – End-to-End-Tests: Metadata-Pipeline und Export."""

from __future__ import annotations

import os
from typing import Tuple

import pandas as pd
import pytest

from app.export import (
    AuditWriter,
    ExportValidator,
    PackageManifestWriter,
    XbrlCsvWriter,
    XmlWriter,
)
from app.metadata import (
    MetadataMapper,
    MetadataQualityChecker,
    MetadataRepository,
    MetadataVersioning,
    PackageLocator,
    PackageReader,
)
from app.models import (
    CanonicalFact,
    ExportPackage,
    MetadataPackage,
    TemplateData,
)
from app.transformation import (
    CanonicalModelBuilder,
    ExportPreparer,
)


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "phase3")
V1 = os.path.join(FIXTURES, "package_v1")
V2 = os.path.join(FIXTURES, "package_v2")


def _load_package(path: str) -> MetadataPackage:
    locator = PackageLocator()
    location = locator.locate(path)
    assert location is not None, f"could not locate package at {path}"
    reader = PackageReader()
    raw = reader.read(location)
    mapper = MetadataMapper()
    return mapper.build_package(raw)


@pytest.fixture
def package_v1() -> MetadataPackage:
    return _load_package(V1)


@pytest.fixture
def package_v2() -> MetadataPackage:
    return _load_package(V2)


def _sample_template_data() -> TemplateData:
    df = pd.DataFrame(
        [
            {
                "c0010": "529900T8BM49AURSDO55",
                "c0020": "2026-03-31",
                "c0030": "EUR",
                "c0040": 1_000_000.50,
            },
            {
                "c0010": "549300DRQQI55N3CZSO4",
                "c0020": "2026-03-31",
                "c0030": "USD",
                "c0040": 250_000.00,
            },
        ]
    )
    return TemplateData(
        template_id="B02.00",
        key="B02.00",
        df=df,
        source_name="sample_input.csv",
    )


# ---------- Locator / Reader ----------


def test_locator_finds_package():
    loc = PackageLocator().locate(V1)
    assert loc is not None
    assert loc.package_id == "EBA-DPM-MINI-v1"
    assert loc.framework_version == "4.2.0"


def test_locator_returns_none_for_invalid_path(tmp_path):
    loc = PackageLocator().locate(str(tmp_path))
    assert loc is None


def test_locator_discover_lists_all(tmp_path):
    found = PackageLocator().discover(FIXTURES)
    assert {p.package_id for p in found} == {"EBA-DPM-MINI-v1", "EBA-DPM-MINI-v2"}


def test_reader_reads_all_artifacts():
    location = PackageLocator().locate(V1)
    raw = PackageReader().read(location)
    assert raw.manifest["package_id"] == "EBA-DPM-MINI-v1"
    assert len(raw.datapoints_rows) == 4
    assert len(raw.templates_rows) == 1
    assert len(raw.codelists_rows) == 2
    assert raw.glossary["LEI"].startswith("Legal Entity")


# ---------- Extractors / Mapper ----------


def test_mapper_builds_package(package_v1: MetadataPackage):
    assert package_v1.framework_version == "4.2.0"
    assert len(package_v1.datapoints) == 4
    assert len(package_v1.templates) == 1
    assert len(package_v1.codelists) == 2
    assert len(package_v1.rules) == 3
    assert any(r.metadata.get("translatable") is False for r in package_v1.rules)


def test_untranslatable_rules_are_marked(package_v1: MetadataPackage):
    legacy = next(r for r in package_v1.rules if r.rule_id == "V_B02_0030_LEGACY")
    assert legacy.metadata["translatable"] is False
    # untranslatable rules have empty DSL fields but keep severity/message
    assert legacy.condition == ""
    assert legacy.assertion == ""
    assert legacy.message != ""


def test_derive_config_includes_codelists(package_v1: MetadataPackage):
    config = MetadataMapper().derive_config(package_v1)
    assert "CL_CURRENCY" in config.codelist_map
    assert "V_B02_0030_LEGACY" in config.untranslatable_rule_ids


# ---------- Repository / Versioning ----------


def test_repository_is_immutable(package_v1: MetadataPackage):
    repo = MetadataRepository()
    repo.register(package_v1)
    with pytest.raises(ValueError):
        repo.register(package_v1)


def test_repository_get_latest_and_versions(
    package_v1: MetadataPackage, package_v2: MetadataPackage
):
    repo = MetadataRepository()
    repo.register(package_v1)
    repo.register(package_v2)
    # both packages have different package_id so latest() returns the matching one
    assert repo.get(package_v1.package_id) is package_v1
    assert repo.get(package_v2.package_id) is package_v2
    assert len(repo.all_packages()) == 2


def test_versioning_delta_detects_changes(
    package_v1: MetadataPackage, package_v2: MetadataPackage
):
    delta = MetadataVersioning().diff(package_v1, package_v2)
    assert delta.has_changes()
    assert "DP_B02_C0050" in delta.datapoints_added
    assert "B02.00" in delta.templates_changed
    assert "CL_CURRENCY" in delta.codelists_changed
    assert set(delta.codelists_value_diff["CL_CURRENCY"]["added"]) == {"JPY", "SEK"}
    assert "V_B02_0040" in delta.rules_added
    assert "V_B02_0020" in delta.rules_changed


# ---------- Quality ----------


def test_quality_clean_package_has_no_errors(package_v1: MetadataPackage):
    report = MetadataQualityChecker().check(package_v1)
    assert not report.has_errors()
    # at least one WARN for the untranslatable rule
    assert any(f.severity == "WARN" for f in report.findings)


def test_quality_detects_unknown_codelist_reference():
    # Build a broken package by hand: datapoint references unknown codelist.
    from app.models import DataPointDefinition

    pkg = MetadataPackage(
        package_id="BROKEN", framework_version="4.2.0",
        datapoints=[
            DataPointDefinition(
                datapoint_id="X", template_id="T", field_code="c0010",
                codelist_id="UNKNOWN_CL", technical_identifier="t:x",
            )
        ],
    )
    report = MetadataQualityChecker().check(pkg)
    assert report.has_errors()
    assert any(f.code == "MD020" for f in report.findings)


# ---------- Transformation ----------


def test_canonical_model_builder_creates_facts(package_v1: MetadataPackage):
    tpl_data = _sample_template_data()
    builder = CanonicalModelBuilder()
    facts = builder.build(tpl_data, package_v1, entity="529900T8BM49AURSDO55")
    # 2 rows * 4 datapoints (all non-null) = 8
    assert len(facts) == 8
    sample = next(f for f in facts if f.field_code == "c0040" and f.source_row == 0)
    assert sample.value == 1_000_000.50
    assert sample.unit == "EUR"
    assert sample.context.entity == "529900T8BM49AURSDO55"
    assert "ENTITY" in sample.dimensions
    assert "PERIOD" in sample.dimensions


def test_export_preparer_sorts_facts(package_v1: MetadataPackage):
    tpl_data = _sample_template_data()
    facts = CanonicalModelBuilder().build(tpl_data, package_v1)
    prepared = ExportPreparer().prepare(facts)
    # sorted by template, field, row
    assert [f.field_code for f in prepared[:2]] == ["c0010", "c0010"]


# ---------- Export validation ----------


def test_export_validator_passes_clean_facts(package_v1: MetadataPackage):
    tpl_data = _sample_template_data()
    facts = CanonicalModelBuilder().build(tpl_data, package_v1)
    issues = ExportValidator().validate(facts, package_v1)
    assert issues == []


def test_export_validator_detects_duplicates(package_v1: MetadataPackage):
    tpl_data = _sample_template_data()
    facts = CanonicalModelBuilder().build(tpl_data, package_v1)
    # Force a duplicate by cloning one fact under a different fact_id.
    clone = CanonicalFact(**{**facts[0].__dict__, "fact_id": "DUP_" + facts[0].fact_id})
    issues = ExportValidator().validate(facts + [clone], package_v1)
    assert any(i.code == "EX050" for i in issues)


def test_export_validator_flags_version_mismatch(package_v1: MetadataPackage):
    tpl_data = _sample_template_data()
    facts = CanonicalModelBuilder().build(tpl_data, package_v1)
    facts[0].metadata_version = "9.9.9"
    issues = ExportValidator().validate(facts, package_v1)
    assert any(i.code == "EX040" for i in issues)


# ---------- Writers ----------


def test_xml_writer_produces_valid_xml(package_v1: MetadataPackage, tmp_path):
    facts = CanonicalModelBuilder().build(_sample_template_data(), package_v1)
    path = tmp_path / "export.xml"
    XmlWriter().write(str(path), facts, package_v1, run_id="R-001")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("<?xml")
    assert "facts" in text
    assert "eba:b02.c0010" in text
    # XML must parse
    from xml.etree import ElementTree as ET
    ET.fromstring(text)


def test_xbrl_csv_writer_writes_package(package_v1: MetadataPackage, tmp_path):
    facts = CanonicalModelBuilder().build(_sample_template_data(), package_v1)
    out_dir = tmp_path / "xbrl"
    result = XbrlCsvWriter().write(str(out_dir), facts, package_v1, run_id="R-002")
    assert (out_dir / "facts.csv").is_file()
    assert (out_dir / "metadata.json").is_file()
    assert (out_dir / "parameters.csv").is_file()
    assert len(result.artifacts) == 3
    # CSV header sanity check
    header = (out_dir / "facts.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "fact_id" in header
    assert "dim_ENTITY" in header


def test_manifest_and_audit_round_trip(package_v1: MetadataPackage, tmp_path):
    facts = CanonicalModelBuilder().build(_sample_template_data(), package_v1)
    out_dir = tmp_path / "exp"
    csv_result = XbrlCsvWriter().write(str(out_dir), facts, package_v1, run_id="R-003")
    audit_writer = AuditWriter()
    input_hash = audit_writer.input_hash([f.to_dict() for f in facts])
    export_pkg = ExportPackage(
        package_id="EXPORT-001",
        export_format="xbrl-csv",
        metadata_version=package_v1.framework_version,
        rule_version=package_v1.framework_version,
        rule_count=len(package_v1.rules),
        input_hash=input_hash,
        run_id="R-003",
        facts=facts,
        artifacts=csv_result.artifacts,
        status="VALIDATED",
    )
    manifest_path = PackageManifestWriter().write(str(out_dir), export_pkg)
    audit_path = audit_writer.write(str(out_dir), export_pkg, facts)
    assert os.path.isfile(manifest_path)
    assert os.path.isfile(audit_path)

    import json
    manifest = json.loads(open(manifest_path).read())
    audit = json.loads(open(audit_path).read())
    assert manifest["fact_count"] == len(facts)
    assert manifest["metadata_version"] == package_v1.framework_version
    assert audit["input_hash"] == input_hash
    assert audit["rule_count"] == len(package_v1.rules)


def test_end_to_end_roundtrip(package_v1: MetadataPackage, tmp_path):
    """Komplett-Roundtrip: package -> facts -> validate -> xml + csv + manifest + audit."""
    facts = CanonicalModelBuilder().build(_sample_template_data(), package_v1)
    facts = ExportPreparer().prepare(facts)
    issues = ExportValidator().validate(facts, package_v1)
    assert issues == []

    xml_path = tmp_path / "out.xml"
    XmlWriter().write(str(xml_path), facts, package_v1, run_id="RT-1")

    csv_dir = tmp_path / "csv"
    csv_result = XbrlCsvWriter().write(str(csv_dir), facts, package_v1, run_id="RT-1")

    audit_writer = AuditWriter()
    input_hash = audit_writer.input_hash([f.to_dict() for f in facts])
    export_pkg = ExportPackage(
        package_id="RT-EXPORT",
        export_format="xbrl-csv",
        metadata_version=package_v1.framework_version,
        rule_version=package_v1.framework_version,
        rule_count=len(package_v1.rules),
        input_hash=input_hash,
        run_id="RT-1",
        facts=facts,
        artifacts=csv_result.artifacts,
        status="VALIDATED",
    )
    PackageManifestWriter().write(str(csv_dir), export_pkg)
    audit_writer.write(str(csv_dir), export_pkg, facts)

    assert xml_path.is_file()
    assert (csv_dir / "facts.csv").is_file()
    assert (csv_dir / "manifest.json").is_file()
    assert (csv_dir / "audit.json").is_file()
