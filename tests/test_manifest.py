"""Tests für das Run-Manifest-Skelett."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import InputBatch, TemplateData, ValidationIssue
from app.reporting.manifest import build_manifest, generate_run_id


def test_generate_run_id_deterministic():
    a = generate_run_id("/tmp/foo", "2024-01-01T00:00:00Z")
    b = generate_run_id("/tmp/foo", "2024-01-01T00:00:00Z")
    c = generate_run_id("/tmp/bar", "2024-01-01T00:00:00Z")
    assert a == b
    assert a != c


def test_build_manifest_round_trip(tmp_path: Path):
    batch = InputBatch(source_type="csv_dir", source_path=str(tmp_path))
    import pandas as pd
    batch.add(TemplateData(template_id="B99.00", key="B99.00", df=pd.DataFrame({"c0010": ["X"]})))
    issues = [
        ValidationIssue(rule_id="R1", rule_level="L1", rule_type="MANDATORY_FIELD",
                        template="B99.00", severity="ERROR", message="m"),
        ValidationIssue(rule_id="R2", rule_level="CL", rule_type="CODELIST_CHECK",
                        template="B99.00", severity="WARNING", message="m"),
    ]
    manifest = build_manifest(
        batch=batch,
        catalog_metadata={"version": "1.5"},
        catalog_rule_count=42,
        issues=issues,
        started_at="2024-01-01T00:00:00Z",
        finished_at="2024-01-01T00:00:05Z",
        de_annex=False,
        run_id="fixed-run-id",
    )
    d = manifest.to_dict()
    assert d["run_id"] == "fixed-run-id"
    assert d["issues"]["count"] == 2
    assert d["issues"]["by_severity"] == {"ERROR": 1, "WARNING": 1}
    assert d["catalog"]["version"] == "1.5"
    assert d["catalog"]["rule_count"] == 42
    assert d["templates_loaded"] == ["B99.00"]


def test_manifest_json_is_deterministic(tmp_path: Path):
    batch = InputBatch(source_type="csv_dir", source_path="")
    issues: list = []
    m1 = build_manifest(
        batch=batch,
        catalog_metadata={"version": "1.5"},
        catalog_rule_count=0,
        issues=issues,
        started_at="2024-01-01T00:00:00Z",
        finished_at="2024-01-01T00:00:01Z",
        run_id="rid",
    )
    m2 = build_manifest(
        batch=batch,
        catalog_metadata={"version": "1.5"},
        catalog_rule_count=0,
        issues=issues,
        started_at="2024-01-01T00:00:00Z",
        finished_at="2024-01-01T00:00:01Z",
        run_id="rid",
    )
    assert m1.to_json() == m2.to_json()
    # JSON ist valide und sorted-keys
    parsed = json.loads(m1.to_json())
    assert parsed["run_id"] == "rid"


def test_manifest_writes_file(tmp_path: Path):
    batch = InputBatch(source_type="csv_dir", source_path="")
    m = build_manifest(
        batch=batch,
        catalog_metadata={"version": "1.5"},
        catalog_rule_count=0,
        issues=[],
        started_at="2024-01-01T00:00:00Z",
        run_id="rid",
    )
    out = m.write(tmp_path / "manifest.json")
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["run_id"] == "rid"
