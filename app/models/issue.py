"""Einheitliches Fehler-/Befundobjekt."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ValidationIssue:
    """Ein einzelner Validierungsbefund.

    Feldnamen sind 1:1 abwärtskompatibel zum bestehenden Dict-Format aus
    ``MBDTValidator._add_error`` – damit kann Reporting wahlweise auf den
    Dataclasses oder den klassischen Dicts arbeiten.
    """

    rule_id: str
    rule_level: str
    rule_type: str
    template: str
    severity: str = "ERROR"
    row: Optional[int] = None
    field_code: str = ""
    field_label: str = ""
    value: str = ""
    message: str = ""
    explanation: str = ""
    dpm_reference: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationIssue":
        return cls(
            rule_id=data.get("rule_id", ""),
            rule_level=data.get("rule_level", ""),
            rule_type=data.get("rule_type", ""),
            template=data.get("template", ""),
            severity=data.get("severity", "ERROR"),
            row=data.get("row"),
            field_code=data.get("field_code", "") or "",
            field_label=data.get("field_label", ""),
            value=("" if data.get("value") is None else str(data.get("value"))),
            message=data.get("message", ""),
            explanation=data.get("explanation", ""),
            dpm_reference=data.get("dpm_reference", ""),
            timestamp=data.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_level": self.rule_level,
            "rule_type": self.rule_type,
            "template": self.template,
            "row": self.row,
            "field_code": self.field_code,
            "field_label": self.field_label,
            "severity": self.severity,
            "value": self.value,
            "message": self.message,
            "explanation": self.explanation,
            "dpm_reference": self.dpm_reference,
            "timestamp": self.timestamp,
        }
