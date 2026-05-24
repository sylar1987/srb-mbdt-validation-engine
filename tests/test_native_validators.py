"""Native-Validator-Tests (Phase 1.5).

Drei Säulen:
1. Native ↔ Legacy: für eine kleine Fixture liefern beide Modi dieselbe
   Issue-Menge (per rule_id / template / row / field_code / severity).
2. Einzelne Validatoren liefern für gezielte Eingaben die erwarteten Issues.
3. Strukturvalidator erkennt unbekannte Felder und fehlende Pflichtspalten.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from app.config.catalog_loader import (
    load_catalog,
    load_field_structure,
    load_field_structure_model,
)
from app.models import InputBatch, RuleDefinition, TemplateData, ValidationIssue
from app.runner import Runner
from app.settings import EngineSettings
from app.validation import codelist_validator, datatype_validator, mandatory_validator
from app.validation.context import ValidationContext
from app.validation.structure_validator import validate_structure


# ── Helpers ───────────────────────────────────────────────────────────────


def _write_csv(path: Path, header: List[str], rows: List[List[str]]) -> None:
    with open(path, "w", encoding="utf-8-sig") as fh:
        fh.write(";".join(header) + "\n")
        for r in rows:
            fh.write(";".join(r) + "\n")


def _mini_fixture(tmp: Path) -> None:
    # B99.00 mit gültigen Pflichtfeldern und Reference Date
    _write_csv(
        tmp / "B99.00.csv",
        ["0010", "0020", "0030", "0050", "0051", "0060", "0070", "0080", "0090"],
        [
            [
                "Bank AG",
                "529900XXXX0000000001",
                "DE",
                "ResEnt",
                "529900XXXX0000000002",
                "Resolution Entity",
                "2024-12-31",
                "EUR",
                "1.0",
            ]
        ],
    )
    # B02.00 mit absichtlichen Fehlern: Pflichtfeld c0030 leer, Codelist-Fehler in c0140,
    # ungültiges Datum in 0070 ist hier nicht direkt, aber c0080 ist gefüllt.
    _write_csv(
        tmp / "B02.00.csv",
        ["0010", "0030", "0040", "0070", "0080", "0140", "0250"],
        [["1", "", "ISIN", "EUR", "1000", "FantasyType", "Non-Structured/Vanilla"]],
    )


def _run(use_native: bool, tmp: Path):
    s = EngineSettings()
    s.extra["use_native_validators"] = use_native
    r = Runner(s)
    r.load_csv_dir(tmp)
    r.validate()
    return r


def _issue_key(it: ValidationIssue) -> Tuple:
    return (it.rule_id, it.template, it.row, it.field_code, it.severity)


# ── 1. Parity native vs legacy ────────────────────────────────────────────


def test_native_and_legacy_produce_same_issue_set(tmp_path: Path):
    _mini_fixture(tmp_path)
    native = _run(True, tmp_path)
    legacy = _run(False, tmp_path)
    native_keys = sorted({_issue_key(i) for i in native.context.issues})
    legacy_keys = sorted({_issue_key(i) for i in legacy.context.issues})
    assert native_keys == legacy_keys


# ── 2. Native validator unit tests ────────────────────────────────────────


def _ctx_with(df_map: dict, catalog=None) -> ValidationContext:
    catalog = catalog or load_catalog()
    batch = InputBatch(source_type="memory", source_path="memory")
    for k, df in df_map.items():
        batch.add(TemplateData(template_id=k.split("_", 1)[0], key=k, df=df))
    return ValidationContext(
        batch=batch,
        catalog=catalog,
        field_structure=load_field_structure(),
        field_structure_model=load_field_structure_model(),
        legacy_validator=None,
        use_native_validators=True,
    )


def test_mandatory_validator_native_detects_empty():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0010": ["1"], "c0030": [""]})})
    rule = RuleDefinition(
        rule_id="T_001",
        rule_level="L1",
        rule_type="MANDATORY_FIELD",
        template="B02.00",
        field_code="c0030",
        field_label="Unique ID",
    )
    issues = mandatory_validator.validate(ctx, rule)
    assert len(issues) == 1
    assert issues[0].rule_id == "T_001"
    assert issues[0].row == 2
    assert issues[0].severity == "ERROR"


def test_mandatory_validator_missing_column_reported():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0010": ["1"]})})
    rule = RuleDefinition(
        rule_id="T_002",
        rule_level="L1",
        rule_type="MANDATORY_FIELD",
        template="B02.00",
        field_code="c0030",
        field_label="Unique ID",
    )
    issues = mandatory_validator.validate(ctx, rule)
    assert len(issues) == 1
    assert "fehlt im Template" in issues[0].message
    assert issues[0].row is None


def test_codelist_validator_native_flags_invalid_value():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0140": ["Other-Bogus"]})})
    rule = RuleDefinition(
        rule_id="T_003",
        rule_level="CL",
        rule_type="CODELIST_CHECK",
        template="B02.00",
        field_code="c0140",
        field_label="Nature of the liability",
        codelist_name="Nature of the liability",
    )
    issues = codelist_validator.validate(ctx, rule)
    assert len(issues) == 1
    assert "Ungültiger Codelist-Wert" in issues[0].message


def test_codelist_validator_tolerates_na():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0140": ["Not applicable"]})})
    rule = RuleDefinition(
        rule_id="T_004",
        rule_level="CL",
        rule_type="CODELIST_CHECK",
        template="B02.00",
        field_code="c0140",
        codelist_name="Nature of the liability",
    )
    assert codelist_validator.validate(ctx, rule) == []


def test_datatype_validator_native_numeric():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0080": ["abc"]})})
    rule = RuleDefinition(
        rule_id="T_005",
        rule_level="DPM",
        rule_type="DATATYPE_CHECK",
        template="B02.00",
        field_code="c0080",
        test_type="Test for numeric values.",
    )
    issues = datatype_validator.validate(ctx, rule)
    assert len(issues) == 1
    assert "Kein Zahlenwert" in issues[0].message


def test_datatype_validator_native_lei():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0020": ["INVALID"]})})
    rule = RuleDefinition(
        rule_id="T_006",
        rule_level="DPM",
        rule_type="FORMAT_CHECK",
        template="B02.00",
        field_code="c0020",
        test_type="LEI format check.",
    )
    issues = datatype_validator.validate(ctx, rule)
    assert len(issues) == 1
    assert "LEI" in issues[0].message


def test_datatype_validator_native_lei_valid_not_rejected_as_numeric():
    """Regressionstest: ein gültiger LEI darf nicht über das Substring
    ``numeric`` im test_type ``"LEI format check (20 alphanumeric
    characters)"`` auf den Numeric-Check misrouted werden.

    Die catalog-konforme test_type-Formulierung enthält das Wort
    ``numeric`` – würde das _select_checker zuerst auf ``numeric``
    matchen, würde der gültige LEI (20 alphanumerische Zeichen) als
    ``"Kein Zahlenwert"`` abgelehnt.
    """
    valid_lei = "529900XXXX0000000001"  # 20 alphanumerisch, ISO 17442
    ctx = _ctx_with({"B99.00": pd.DataFrame({"c0020": [valid_lei]})})
    rule = RuleDefinition(
        rule_id="T_LEI_VALID",
        rule_level="DPM",
        rule_type="FORMAT_CHECK",
        template="B99.00",
        field_code="c0020",
        # exakte Catalog-Formulierung
        test_type="LEI format check (20 alphanumeric characters)",
    )
    issues = datatype_validator.validate(ctx, rule)
    assert issues == [], (
        f"Gültiger LEI '{valid_lei}' wurde fälschlich abgelehnt: "
        f"{[i.message for i in issues]}"
    )


def test_datatype_validator_select_checker_routes_lei_before_numeric():
    """Direkter Unit-Test der Routing-Reihenfolge im _select_checker.

    Selbst wenn ``numeric`` als Substring im test_type vorkommt, muss
    der spezifische LEI-Checker gewählt werden, sobald ``lei`` ebenfalls
    enthalten ist.
    """
    from app.validation.datatype_validator import (
        _lei_check,
        _select_checker,
    )

    fn, out_type = _select_checker("LEI format check (20 alphanumeric characters)")
    assert fn is _lei_check
    assert out_type == "FORMAT_CHECK"


def test_datatype_validator_native_lei_invalid_with_catalog_test_type():
    """Negativtest mit exakter Catalog-Formulierung: ein zu kurzer
    Wert muss als LEI-Format-Fehler (nicht als Numeric-Fehler) gemeldet
    werden."""
    ctx = _ctx_with({"B99.00": pd.DataFrame({"c0020": ["SHORT123"]})})
    rule = RuleDefinition(
        rule_id="T_LEI_SHORT",
        rule_level="DPM",
        rule_type="FORMAT_CHECK",
        template="B99.00",
        field_code="c0020",
        test_type="LEI format check (20 alphanumeric characters)",
    )
    issues = datatype_validator.validate(ctx, rule)
    assert len(issues) == 1
    assert "LEI-Format" in issues[0].message
    assert "Kein Zahlenwert" not in issues[0].message
    assert issues[0].rule_type == "FORMAT_CHECK"


def test_datatype_validator_native_iso_currency():
    ctx = _ctx_with({"B02.00": pd.DataFrame({"c0070": ["XYZ"]})})
    rule = RuleDefinition(
        rule_id="T_007",
        rule_level="DPM",
        rule_type="FORMAT_CHECK",
        template="B02.00",
        field_code="c0070",
        test_type="ISO 4217 currency.",
    )
    issues = datatype_validator.validate(ctx, rule)
    assert len(issues) == 1
    assert "ISO 4217" in issues[0].message


# ── 3. Structure validator ────────────────────────────────────────────────


def test_structure_validator_unknown_field():
    ctx = _ctx_with({"B99.00": pd.DataFrame({"c0010": ["X"], "c9999": ["?"]})})
    issues = validate_structure(ctx)
    unknown = [i for i in issues if i.rule_id == "STRUCT_002"]
    assert any(i.field_code == "c9999" for i in unknown)


def test_structure_validator_missing_mandatory_column():
    ctx = _ctx_with({"B99.00": pd.DataFrame({"c0010": ["X"]})})  # ohne c0070 etc.
    issues = validate_structure(ctx)
    missing = [i for i in issues if i.rule_id == "STRUCT_003"]
    assert any(i.field_code == "c0070" for i in missing)


def test_structure_validator_unknown_template():
    ctx = _ctx_with({"B77.99": pd.DataFrame({"c0010": ["X"]})})
    issues = validate_structure(ctx)
    assert any(i.rule_id == "STRUCT_001" and i.template == "B77.99" for i in issues)
