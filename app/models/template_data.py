"""Repräsentation eines einzelnen geladenen Templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class TemplateData:
    """Container für ein einzelnes geladenes Template.

    ``template_id`` ist die normalisierte ID (z. B. ``B02.00``).
    ``key`` ist der eindeutige Schlüssel inkl. Variante (z. B. ``B02.00_TypeA``).
    """

    template_id: str
    key: str
    df: pd.DataFrame
    variant: Optional[str] = None
    source_name: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return 0 if self.df is None else len(self.df)

    def to_debug_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "key": self.key,
            "variant": self.variant,
            "source_name": self.source_name,
            "rows": self.row_count,
            "columns": list(self.df.columns) if self.df is not None else [],
        }
