"""Eingabe-Batch – fasst alle geladenen Templates einer Submission zusammen."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, Optional

import pandas as pd

from app.models.template_data import TemplateData


@dataclass
class InputBatch:
    """Aggregat aller Templates einer Submission.

    Felder spiegeln die historischen Eigenschaften des Validators wider:
    ``templates`` als Map ``key -> DataFrame`` (kompatibel zu ``self.templates``),
    plus typsichere ``TemplateData``-Objekte.
    """

    source_type: str = ""  # "xlsx" | "csv_dir" | "csv_file"
    source_path: str = ""
    entity_name: str = ""
    reference_date: str = ""
    templates: Dict[str, pd.DataFrame] = field(default_factory=dict)
    template_objects: Dict[str, TemplateData] = field(default_factory=dict)

    def add(self, template_data: TemplateData) -> None:
        self.templates[template_data.key] = template_data.df
        self.template_objects[template_data.key] = template_data

    def keys(self):
        return self.templates.keys()

    def __iter__(self) -> Iterator[str]:
        return iter(self.templates)

    def __contains__(self, item: object) -> bool:
        return item in self.templates

    def get(self, key: str) -> Optional[pd.DataFrame]:
        return self.templates.get(key)

    def to_debug_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "source_path": self.source_path,
            "entity_name": self.entity_name,
            "reference_date": self.reference_date,
            "templates": {k: td.to_debug_dict() for k, td in self.template_objects.items()},
        }
