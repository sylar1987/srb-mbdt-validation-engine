"""Tests für ``catalog_loader``."""

from __future__ import annotations

from app.config import load_catalog


def test_catalog_loads_with_rules():
    cat = load_catalog()
    assert len(cat.rules) > 0
    assert all(r.rule_id for r in cat.rules)
    # Codelisten sollen mind. die zentralen MBDT-Listen enthalten.
    assert any("Nature" in name for name in cat.codelists.keys())


def test_catalog_de_annex_overrides():
    cat = load_catalog(de_annex=True)
    if "DE_Nature of the liability" in cat.codelists:
        assert cat.codelists["Nature of the liability"] == \
            cat.codelists["DE_Nature of the liability"]
