"""Phase-2-Regelmodell: ``RuleDefinitionV2``.

Dieses Modell wird in Phase 2 parallel zu ``RuleDefinition`` eingeführt.
Es trennt klar zwischen **Bedingung** (``condition``, wann gilt die Regel?)
und **Aussage** (``assertion``, was muss zutreffen, wenn die Bedingung
erfüllt ist?). Beide werden als DSL-Strings gespeichert und vom Parser in
einen AST überführt.

Die Konvertierung aus ``RuleDefinition`` ist verlustarm gestaltet:
nicht abbildbare Regeltypen liefern ``None`` und werden vom Aufrufer
explizit protokolliert (siehe ``map_legacy_rule``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.models.rule import RuleDefinition


VALID_SCOPES = ("row", "template", "cross")


@dataclass
class RuleDefinitionV2:
    """DSL-orientiertes Regelmodell für Phase 2 und Phase 3.

    Felder:
      - ``rule_id``: stabile, eindeutige Regel-ID
      - ``scope``: ``row`` | ``template`` | ``cross``
      - ``target_template``: Template, in dessen Kontext die Regel ausgewertet
        wird (z. B. ``B02.00``); leer für template-übergreifende Regeln
      - ``condition``: DSL-Ausdruck; wenn ``True``, ist die Regel anwendbar.
        Leer bedeutet ``immer anwendbar``.
      - ``assertion``: DSL-Ausdruck; wenn ``False``, wird eine Issue erzeugt.
        Leer bedeutet, dass nur eine Existenzprüfung greift (Migration
        bestehender L1-MANDATORY-Regeln).
      - ``severity``: ``ERROR`` | ``WARN`` | ``INFO``
      - ``message``: Vorlagentext für Issues; darf Platzhalter ``{field}``
        oder ``{value}`` enthalten
      - ``source``: Herkunft, z. B. ``legacy:rule_catalog.json`` oder
        ``dpm:EBA-4.2`` (Phase 3)
      - ``metadata``: Freie Map für Phase-3-Erweiterungen (Rule-Family,
        DPM-Reference, ...)
    """

    rule_id: str
    scope: str = "row"
    target_template: str = ""
    condition: str = ""
    assertion: str = ""
    severity: str = "ERROR"
    message: str = ""
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scope not in VALID_SCOPES:
            raise ValueError(
                f"Unsupported scope '{self.scope}'. "
                f"Allowed: {VALID_SCOPES}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "scope": self.scope,
            "target_template": self.target_template,
            "condition": self.condition,
            "assertion": self.assertion,
            "severity": self.severity,
            "message": self.message,
            "source": self.source,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleDefinitionV2":
        return cls(
            rule_id=data["rule_id"],
            scope=data.get("scope", "row"),
            target_template=data.get("target_template", ""),
            condition=data.get("condition", ""),
            assertion=data.get("assertion", ""),
            severity=data.get("severity", "ERROR"),
            message=data.get("message", ""),
            source=data.get("source", ""),
            metadata=dict(data.get("metadata") or {}),
        )


_PREREQ_PREFIX = re.compile(
    r"^\s*Rule applicable(?:\s+only)?\s+if\s+", re.IGNORECASE
)


def translate_legacy_prerequisite(text: str) -> Optional[str]:
    """Übersetzt ``Rule applicable if ...``-Strings nach DSL.

    Liefert ``None`` für nicht abbildbare Texte. Die Übersetzung deckt
    die in ``rule_catalog.json`` real vorkommenden Muster ab:

      - ``cNNNN = "X"``  → ``cNNNN = "X"``
      - ``cNNNN != "X"`` → ``cNNNN != "X"``
      - ``cNNNN = ("A" OR "B")`` → ``cNNNN in ("A", "B")``
      - ``cNNNN != ("A" OR "B")`` → ``cNNNN not in ("A", "B")``
      - Verbindung mit ``AND``
    """
    if not text or not text.strip():
        return ""

    body = _PREREQ_PREFIX.sub("", text).strip()
    body = body.rstrip(".")
    if not body:
        return None

    parts = re.split(r"\s+AND\s+", body, flags=re.IGNORECASE)
    translated_parts: List[str] = []
    for part in parts:
        translated = _translate_atom(part.strip())
        if translated is None:
            return None
        translated_parts.append(translated)

    return " and ".join(translated_parts)


_ATOM_PATTERN = re.compile(
    r"^(c\d{4})\s*(=|!=)\s*(.+)$", re.IGNORECASE
)


def _translate_atom(atom: str) -> Optional[str]:
    m = _ATOM_PATTERN.match(atom)
    if not m:
        return None

    field_code = m.group(1).lower()
    op = m.group(2)
    rhs = m.group(3).strip()

    if rhs.startswith("(") and rhs.endswith(")"):
        inner = rhs[1:-1]
        values = re.split(r"\s+OR\s+", inner, flags=re.IGNORECASE)
        cleaned = [_normalize_string_literal(v.strip()) for v in values]
        if any(c is None for c in cleaned):
            return None
        joined = ", ".join(cleaned)  # type: ignore[arg-type]
        operator = "in" if op == "=" else "not in"
        return f"{field_code} {operator} ({joined})"

    literal = _normalize_string_literal(rhs)
    if literal is None:
        return None
    return f"{field_code} {op} {literal}"


def _normalize_string_literal(raw: str) -> Optional[str]:
    raw = raw.strip()
    if not raw:
        return None
    if raw.startswith('"') and raw.endswith('"'):
        return raw
    if raw.startswith("'") and raw.endswith("'"):
        inner = raw[1:-1].replace('"', '\\"')
        return f'"{inner}"'
    if re.match(r"^-?\d+(?:\.\d+)?$", raw):
        return raw
    if raw.lower() in ("true", "false", "null"):
        return raw.lower()
    escaped = raw.replace('"', '\\"')
    return f'"{escaped}"'


def map_legacy_rule(rule: RuleDefinition) -> Optional[RuleDefinitionV2]:
    """Mappt eine Phase-1-``RuleDefinition`` nach ``RuleDefinitionV2``.

    Liefert ``None``, wenn der Prerequisite-String nicht sauber in DSL
    übersetzbar ist. Der Aufrufer entscheidet, ob die Regel dann mit
    Phase-1-Fallback ausgewertet wird.
    """
    if not rule.rule_id:
        return None

    condition = translate_legacy_prerequisite(rule.prerequisite)
    if condition is None:
        return None

    assertion = ""
    if rule.rule_type == "MANDATORY_FIELD" and rule.field_code:
        assertion = f"is_not_null({rule.field_code.lower()})"

    metadata = {
        "rule_level": rule.rule_level,
        "rule_type": rule.rule_type,
        "field_code": rule.field_code,
        "field_label": rule.field_label,
        "dpm_reference": rule.dpm_reference,
        "de_only": rule.de_only,
    }
    if rule.codelist_name:
        metadata["codelist_name"] = rule.codelist_name
    if rule.codelist_values:
        metadata["codelist_values"] = list(rule.codelist_values)

    scope = "row"
    if rule.rule_level == "CROSS":
        scope = "cross"

    return RuleDefinitionV2(
        rule_id=rule.rule_id,
        scope=scope,
        target_template=rule.template,
        condition=condition,
        assertion=assertion,
        severity=rule.severity or "ERROR",
        message=rule.explanation or "",
        source="legacy:rule_catalog.json",
        metadata=metadata,
    )
