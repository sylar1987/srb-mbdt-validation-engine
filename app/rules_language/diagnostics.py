"""Diagnose-Codes und Fehlerklassen für die DSL.

Die DSL signalisiert Probleme über strukturierte Diagnosen, damit der Aufrufer
sie in ``ValidationIssue`` umwandeln kann. Jede Diagnose trägt einen ``code``
(siehe ``docs/PHASE2_DSL_SPEC.md`` Abschnitt „Diagnostik“).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class DiagnosticCode(str, Enum):
    SYNTAX = "DSL_SYNTAX"
    UNSUPPORTED_FN = "DSL_UNSUPPORTED_FN"
    UNKNOWN_FIELD = "DSL_UNKNOWN_FIELD"
    UNKNOWN_TEMPLATE = "DSL_UNKNOWN_TEMPLATE"
    TYPE_ERROR = "DSL_TYPE_ERROR"


@dataclass
class Diagnostic:
    code: DiagnosticCode
    message: str
    position: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        loc = f" at {self.position}" if self.position is not None else ""
        return f"[{self.code.value}{loc}] {self.message}"


class DSLError(Exception):
    """Basis für alle DSL-bezogenen Fehler."""

    def __init__(self, diagnostic: Diagnostic):
        super().__init__(str(diagnostic))
        self.diagnostic = diagnostic


class SyntaxError(DSLError):  # noqa: A001 – wir wollen die fachliche Bedeutung
    def __init__(self, message: str, position: Optional[int] = None):
        super().__init__(Diagnostic(DiagnosticCode.SYNTAX, message, position))


class UnsupportedFunctionError(DSLError):
    def __init__(self, name: str, position: Optional[int] = None):
        super().__init__(
            Diagnostic(
                DiagnosticCode.UNSUPPORTED_FN,
                f"Unsupported function: {name}",
                position,
                {"name": name},
            )
        )


class UnknownFieldError(DSLError):
    def __init__(self, field_code: str, template: str = ""):
        super().__init__(
            Diagnostic(
                DiagnosticCode.UNKNOWN_FIELD,
                f"Unknown field: {field_code}" + (f" in {template}" if template else ""),
                None,
                {"field": field_code, "template": template},
            )
        )


class UnknownTemplateError(DSLError):
    def __init__(self, template: str):
        super().__init__(
            Diagnostic(
                DiagnosticCode.UNKNOWN_TEMPLATE,
                f"Unknown template: {template}",
                None,
                {"template": template},
            )
        )


class TypeError(DSLError):  # noqa: A001
    def __init__(self, message: str):
        super().__init__(Diagnostic(DiagnosticCode.TYPE_ERROR, message))
