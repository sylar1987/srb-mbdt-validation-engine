"""Typisierte Sicht auf ``field_structure.json``.

Phase 1.5: Das JSON wird nicht mehr nur als ``dict`` durchgereicht, sondern
in ein dataclass-basiertes Modell überführt. Native Validatoren können
dadurch direkt auf Datentyp, Constraint und Pflichtfeldmarkierung
zugreifen, ohne erneut JSON-Strings zu interpretieren.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class FieldDefinition:
    """Einzelne Feldbeschreibung aus ``field_structure.json``."""

    field_code: str
    column: str
    label: str
    data_type: str = ""
    constraint: str = ""
    mandatory: bool = False

    @property
    def is_lei(self) -> bool:
        return "lei" in self.constraint.lower()

    @property
    def is_iso_currency(self) -> bool:
        return "iso 4217" in self.constraint.lower()

    @property
    def is_iso_country(self) -> bool:
        return "iso 3166" in self.constraint.lower()

    @property
    def is_date(self) -> bool:
        return self.data_type.lower() == "date"

    @property
    def is_numeric(self) -> bool:
        return self.data_type.lower() in ("numeric", "monetary", "integer", "decimal")

    @property
    def is_dropdown(self) -> bool:
        return "drop-down" in self.constraint.lower() or "dropdown" in self.constraint.lower()


@dataclass
class TemplateStructure:
    """Strukturierte Beschreibung eines einzelnen Templates."""

    template_id: str
    fields: List[FieldDefinition] = field(default_factory=list)
    _by_code: Dict[str, FieldDefinition] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._by_code = {f.field_code: f for f in self.fields}

    def get(self, field_code: str) -> Optional[FieldDefinition]:
        if field_code in self._by_code:
            return self._by_code[field_code]
        alt = field_code[1:] if field_code.startswith("c") else f"c{field_code}"
        if alt in self._by_code:
            return self._by_code[alt]
        normalized = f"c{field_code.lstrip('c').zfill(4)}"
        return self._by_code.get(normalized)

    def mandatory_fields(self) -> List[FieldDefinition]:
        return [f for f in self.fields if f.mandatory]

    def known_field_codes(self) -> List[str]:
        return [f.field_code for f in self.fields]


@dataclass
class FieldStructure:
    """Gesamtmodell ``template_id -> TemplateStructure``."""

    templates: Dict[str, TemplateStructure] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Optional[dict]) -> "FieldStructure":
        """Akzeptiert beide Schemavarianten im Repository:

        - ``field_code``/``column``/``mandatory``  (B99, B01, B05, B06)
        - ``code``/``col_number``                  (B02, B03, B04, B90)
        """
        if not raw:
            return cls()
        templates: Dict[str, TemplateStructure] = {}
        for tpl_id, entries in raw.items():
            fields_list: List[FieldDefinition] = []
            for entry in entries or []:
                field_code = str(entry.get("field_code") or entry.get("code") or "")
                column = str(entry.get("column") or entry.get("col_number") or "")
                fields_list.append(
                    FieldDefinition(
                        field_code=field_code,
                        column=column,
                        label=str(entry.get("label", "")),
                        data_type=str(entry.get("data_type", "")),
                        constraint=str(entry.get("constraint", "")),
                        mandatory=bool(entry.get("mandatory", False)),
                    )
                )
            templates[tpl_id] = TemplateStructure(template_id=tpl_id, fields=fields_list)
        return cls(templates=templates)

    def get(self, template_id: str) -> Optional[TemplateStructure]:
        if template_id in self.templates:
            return self.templates[template_id]
        # Variant-Fallback: B02.00_TypeA → B02.00
        if "_" in template_id:
            base = template_id.split("_", 1)[0]
            return self.templates.get(base)
        return None

    def known_template_ids(self) -> Iterable[str]:
        return self.templates.keys()
