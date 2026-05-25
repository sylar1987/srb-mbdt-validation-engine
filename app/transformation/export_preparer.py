"""Bereitet die Liste von Facts für den Export auf (Sortierung, Filterung)."""

from __future__ import annotations

from typing import Iterable, List

from app.models import CanonicalFact


class ExportPreparer:
    def prepare(self, facts: Iterable[CanonicalFact]) -> List[CanonicalFact]:
        """Stabil sortiert nach Template, Field, Source-Row."""
        valid = [f for f in facts if f.validation_status != "INVALID"]
        return sorted(
            valid,
            key=lambda f: (f.template_id, f.field_code, f.source_row),
        )
