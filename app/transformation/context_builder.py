"""Baut ``Context``-Objekte aus Reference-Date/Entity-Informationen."""

from __future__ import annotations

from typing import Optional

from app.models import Context


class ContextBuilder:
    def build(
        self,
        entity: str = "",
        reference_date: str = "",
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        scenario: str = "",
    ) -> Context:
        return Context(
            entity=entity or "",
            period_start=(period_start or reference_date or ""),
            period_end=(period_end or reference_date or ""),
            scenario=scenario,
            reference_date=reference_date or "",
        )
