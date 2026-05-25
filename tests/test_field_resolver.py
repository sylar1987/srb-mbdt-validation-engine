"""Tests für DPM-Feldauflösung (cNNNN vs. cNNNN + Caption vs. Caption-only)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.config.catalog_loader import load_field_structure_model
from app.normalization.field_resolver import (
    FieldResolver,
    extract_field_code_from_header,
    resolve_dataframe_columns,
)
from app.normalization.headers import normalize_col_names
from app.quality.catalog_conformance import check_catalog


# ── extract_field_code_from_header ──────────────────────────────────────

def test_extract_plain_c_code():
    assert extract_field_code_from_header("c0040") == ("c0040", None)
    assert extract_field_code_from_header("C0040") == ("c0040", None)


def test_extract_digit_only():
    assert extract_field_code_from_header("0040") == ("c0040", None)
    assert extract_field_code_from_header("40") == ("c0040", None)
    assert extract_field_code_from_header("5000") == ("c5000", None)


def test_extract_code_plus_caption_ascii_dash():
    code, caption = extract_field_code_from_header("c0040 - Type of identifier")
    assert code == "c0040"
    assert caption == "Type of identifier"


def test_extract_code_plus_caption_en_dash():
    code, caption = extract_field_code_from_header("c0040 – Type of identifier")
    assert code == "c0040"
    assert caption == "Type of identifier"


def test_extract_code_plus_caption_em_dash():
    code, caption = extract_field_code_from_header("c0040 — Type of identifier")
    assert code == "c0040"
    assert caption == "Type of identifier"


def test_extract_code_plus_caption_colon():
    code, caption = extract_field_code_from_header("c0040: Type of identifier")
    assert code == "c0040"
    assert caption == "Type of identifier"


def test_extract_code_plus_caption_parentheses():
    code, caption = extract_field_code_from_header("c0040 (Type of identifier)")
    assert code == "c0040"
    assert caption == "Type of identifier"


def test_extract_digit_plus_caption():
    code, caption = extract_field_code_from_header("0040 - Type of identifier")
    assert code == "c0040"
    assert caption == "Type of identifier"


def test_extract_caption_only_returns_no_code():
    code, caption = extract_field_code_from_header("Type of identifier")
    assert code is None
    assert caption == "Type of identifier"


def test_extract_empty_returns_none():
    assert extract_field_code_from_header("") == (None, None)
    assert extract_field_code_from_header(None) == (None, None)


# ── normalize_col_names mit kombinierten Headern ────────────────────────

def test_normalize_col_names_handles_code_plus_caption():
    out = normalize_col_names([
        "c0010",
        "c0040 - Type of identifier",
        "0070 (Contract Currency)",
    ])
    assert out == ["c0010", "c0040", "c0070"]


def test_normalize_col_names_keeps_caption_only_for_now():
    out = normalize_col_names(["Type of identifier"])
    assert out == ["Type of identifier"]


def test_normalize_col_names_dedup_after_resolution():
    out = normalize_col_names(["c0040", "c0040 - Caption", "0040"])
    assert out == ["c0040", "c0040_1", "c0040_2"]


# ── FieldResolver + field_structure.json ────────────────────────────────

def test_field_resolver_unique_caption_maps_to_code():
    fs_model = load_field_structure_model()
    resolver = FieldResolver("B02.00", fs_model)
    # B02.00 c0040 = "Type of the unique identifier (known to the counterparty)"
    code, reason = resolver.resolve_header(
        "Type of the unique identifier (known to the counterparty)"
    )
    assert code == "c0040"
    assert reason == "caption"


def test_field_resolver_code_takes_precedence_over_caption():
    fs_model = load_field_structure_model()
    resolver = FieldResolver("B02.00", fs_model)
    code, reason = resolver.resolve_header("c0040 - Anything")
    assert code == "c0040"
    assert reason == "code+caption"


def test_field_resolver_ambiguous_caption_is_not_mapped():
    # Künstliche FS: zwei Codes mit identischem Label
    resolver = FieldResolver(
        "DUMMY",
        field_label_pairs=[("c0010", "Foo"), ("c0020", "Foo")],
    )
    code, reason = resolver.resolve_header("Foo")
    assert code is None
    assert reason == "caption_ambiguous"


def test_field_resolver_unknown_caption():
    resolver = FieldResolver(
        "DUMMY", field_label_pairs=[("c0010", "Foo")]
    )
    code, reason = resolver.resolve_header("Bar")
    assert code is None
    assert reason == "unknown"


# ── resolve_dataframe_columns ───────────────────────────────────────────

def test_resolve_dataframe_columns_pure_codes():
    fs_model = load_field_structure_model()
    df = pd.DataFrame({"c0010": ["1"], "c0040": ["X"]})
    out, diag = resolve_dataframe_columns(df, "B02.00", fs_model)
    assert list(out.columns) == ["c0010", "c0040"]
    assert all(d["reason"] == "code" for d in diag)


def test_resolve_dataframe_columns_code_plus_caption():
    fs_model = load_field_structure_model()
    df = pd.DataFrame({
        "c0010 - Row number": ["1"],
        "c0040 – Type of identifier": ["ISIN"],
    })
    out, diag = resolve_dataframe_columns(df, "B02.00", fs_model)
    assert list(out.columns) == ["c0010", "c0040"]
    assert all(d["reason"] == "code+caption" for d in diag)


def test_resolve_dataframe_columns_caption_only():
    fs_model = load_field_structure_model()
    df = pd.DataFrame({
        "Row number": ["1"],
        "Type of the unique identifier (known to the counterparty)": ["ISIN"],
    })
    out, diag = resolve_dataframe_columns(df, "B02.00", fs_model)
    assert "c0010" in out.columns
    assert "c0040" in out.columns
    assert {d["reason"] for d in diag} == {"caption"}


def test_resolve_dataframe_columns_caption_ambiguous_not_renamed():
    # FS-Modell mit künstlichem Konflikt
    from app.models.field_structure import FieldDefinition, FieldStructure, TemplateStructure

    tpl = TemplateStructure(
        template_id="DUMMY",
        fields=[
            FieldDefinition(field_code="c0010", column="0010", label="Foo"),
            FieldDefinition(field_code="c0020", column="0020", label="Foo"),
        ],
    )
    fs = FieldStructure(templates={"DUMMY": tpl})
    df = pd.DataFrame({"Foo": ["x"]})
    out, diag = resolve_dataframe_columns(df, "DUMMY", fs)
    # Ambiguous → Header bleibt unverändert
    assert list(out.columns) == ["Foo"]
    assert diag[0]["reason"] == "caption_ambiguous"


# ── Katalog-Quality-Check ───────────────────────────────────────────────

def test_catalog_conformance_clean_for_repo_catalog():
    repo_root = Path(__file__).resolve().parent.parent
    with open(repo_root / "rule_catalog.json", encoding="utf-8") as fh:
        catalog = json.load(fh)
    with open(repo_root / "field_structure.json", encoding="utf-8") as fh:
        fs = json.load(fh)
    report = check_catalog(catalog, fs)
    # Es dürfen keine harten Fehler vorliegen.
    hard = [f for f in report.findings if f.code != "LABEL_MISMATCH"]
    assert hard == [], f"Auflösbarkeit fehlerhaft: {hard[:5]}"
    assert report.rules_checked == report.rules_resolved


def test_catalog_conformance_detects_unknown_field():
    catalog = {
        "rules": [
            {"rule_id": "x1", "template": "B02.00", "field_code": "c9999",
             "field_label": "Bogus"}
        ]
    }
    fs = {"B02.00": [{"field_code": "c0010", "label": "Row number"}]}
    report = check_catalog(catalog, fs)
    assert len(report.by_code("UNKNOWN_FIELD_CODE")) == 1


def test_catalog_conformance_detects_non_technical_code():
    catalog = {
        "rules": [
            {"rule_id": "x1", "template": "B02.00", "field_code": "Row number",
             "field_label": "Row number"}
        ]
    }
    fs = {"B02.00": [{"field_code": "c0010", "label": "Row number"}]}
    report = check_catalog(catalog, fs)
    assert len(report.by_code("NON_TECHNICAL_FIELD_CODE")) == 1


# ── Integration mit CSV-Loader ──────────────────────────────────────────

def test_csv_loader_accepts_code_plus_caption(tmp_path):
    from app.io import load_csv_dir
    csv = tmp_path / "B02.00.csv"
    csv.write_text(
        "c0010 - Row number;c0040 - Type of identifier\n"
        "1;ISIN\n",
        encoding="utf-8",
    )
    fs_model = load_field_structure_model()
    batch = load_csv_dir(tmp_path, field_structure=fs_model)
    df = batch.templates["B02.00"]
    assert "c0010" in df.columns
    assert "c0040" in df.columns


def test_csv_loader_accepts_caption_only(tmp_path):
    from app.io import load_csv_dir
    csv = tmp_path / "B02.00.csv"
    csv.write_text(
        "Row number;Type of the unique identifier (known to the counterparty)\n"
        "1;ISIN\n",
        encoding="utf-8",
    )
    fs_model = load_field_structure_model()
    batch = load_csv_dir(tmp_path, field_structure=fs_model)
    df = batch.templates["B02.00"]
    assert "c0010" in df.columns
    assert "c0040" in df.columns


def test_csv_loader_without_fs_keeps_caption_only(tmp_path):
    """Ohne field_structure bleiben reine Captions unverändert (keine
    stillen Mappings)."""
    from app.io import load_csv_dir
    csv = tmp_path / "B02.00.csv"
    csv.write_text(
        "Row number;Type of the unique identifier\n1;ISIN\n",
        encoding="utf-8",
    )
    batch = load_csv_dir(tmp_path)  # ohne field_structure
    df = batch.templates["B02.00"]
    assert "Row number" in df.columns
