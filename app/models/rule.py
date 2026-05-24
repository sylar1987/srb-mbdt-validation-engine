"""Typisierte Repräsentation einer Regel aus ``rule_catalog.json``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RuleDefinition:
    """Strukturierte Sicht auf einen JSON-Regeleintrag.

    Die ``raw``-Map bleibt erhalten, damit die bestehende Legacy-Logik die
    Regel in unveränderter Form konsumieren kann (Phase-1-Kompatibilität).
    """

    rule_id: str
    rule_level: str
    rule_type: str
    template: str = ""
    field_code: str = ""
    field_label: str = ""
    severity: str = "ERROR"
    test_type: str = ""
    prerequisite: str = ""
    explanation: str = ""
    dpm_reference: str = ""
    codelist_name: Optional[str] = None
    codelist_values: list = field(default_factory=list)
    de_only: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleDefinition":
        return cls(
            rule_id=data.get("rule_id", ""),
            rule_level=data.get("rule_level", ""),
            rule_type=data.get("rule_type", ""),
            template=data.get("template", ""),
            field_code=data.get("field_code", ""),
            field_label=data.get("field_label", ""),
            severity=data.get("severity", "ERROR"),
            test_type=data.get("test_type", ""),
            prerequisite=data.get("prerequisite", ""),
            explanation=data.get("explanation", ""),
            dpm_reference=data.get("dpm_reference", ""),
            codelist_name=data.get("codelist_name"),
            codelist_values=list(data.get("codelist_values") or []),
            de_only=bool(data.get("de_only", False)),
            raw=dict(data),
        )

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Liefert das ursprüngliche JSON-Dict (für Legacy-Validator-Aufrufe)."""
        return self.raw
