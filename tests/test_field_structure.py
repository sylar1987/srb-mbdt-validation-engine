"""Tests für das typisierte FieldStructure-Modell."""

from __future__ import annotations

from app.config.catalog_loader import load_field_structure_model
from app.models import FieldStructure


def test_field_structure_loads_known_template():
    fs = load_field_structure_model()
    b99 = fs.get("B99.00")
    assert b99 is not None
    assert "c0010" in b99.known_field_codes()
    c0070 = b99.get("c0070")
    assert c0070 is not None
    assert c0070.is_date
    assert c0070.mandatory is True


def test_field_structure_variant_fallback():
    fs = load_field_structure_model()
    # B02.00_TypeA fällt auf B02.00 zurück
    base = fs.get("B02.00")
    via_variant = fs.get("B02.00_TypeA")
    assert base is not None
    assert via_variant is base


def test_field_structure_from_empty_dict():
    fs = FieldStructure.from_dict(None)
    assert list(fs.known_template_ids()) == []
    assert fs.get("any") is None


def test_field_definition_constraint_flags():
    fs = load_field_structure_model()
    b99 = fs.get("B99.00")
    lei = b99.get("c0020")
    assert lei.is_lei
    cur = b99.get("c0080")
    assert cur.is_iso_currency
    country = b99.get("c0030")
    assert country.is_iso_country
