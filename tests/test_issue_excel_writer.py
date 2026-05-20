"""Tests für den Standalone Issue-Excel-Writer (Phase 1.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models import ValidationIssue, ValidationSummary
from app.reporting import write_issue_excel

openpyxl = pytest.importorskip("openpyxl")


def test_write_issue_excel_creates_three_sheets(tmp_path: Path):
    issues = [
        ValidationIssue(
            rule_id="R1", rule_level="L1", rule_type="MANDATORY_FIELD",
            template="B99.00", severity="ERROR", row=2, field_code="c0010",
            message="Pflichtfeld leer",
        ),
    ]
    summary = ValidationSummary.from_issues(issues, ["B99.00"])
    out = tmp_path / "report.xlsx"
    write_issue_excel(issues, out, summary=summary)
    assert out.exists()
    wb = openpyxl.load_workbook(out)
    assert set(wb.sheetnames) == {"Issues", "Summary", "Manifest"}
    ws = wb["Issues"]
    # Header + 1 Datenzeile
    assert ws.max_row == 2
    assert ws.cell(row=2, column=1).value == "R1"
