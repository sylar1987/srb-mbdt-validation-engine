"""Konfigurations-Loader (rule_catalog.json, field_structure.json)."""

from app.config.catalog_loader import (
    Catalog,
    load_catalog,
    load_field_structure,
)

__all__ = ["Catalog", "load_catalog", "load_field_structure"]
