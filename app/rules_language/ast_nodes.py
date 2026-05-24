"""AST-Knotenklassen für die DSL.

Alle Knoten sind ``frozen``-Dataclasses, sodass sie hashbar sind und sich
deterministisch serialisieren lassen (``serializer.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple, Union


@dataclass(frozen=True)
class NumberLiteral:
    value: Union[int, float]


@dataclass(frozen=True)
class StringLiteral:
    value: str


@dataclass(frozen=True)
class BoolLiteral:
    value: bool


@dataclass(frozen=True)
class NullLiteral:
    pass


@dataclass(frozen=True)
class FieldRef:
    """Referenz auf eine Spalte. ``template`` ist leer für Row-Scope."""
    field_code: str
    template: str = ""


@dataclass(frozen=True)
class TemplateRef:
    template: str


@dataclass(frozen=True)
class ListExpr:
    items: Tuple["ASTNode", ...]


@dataclass(frozen=True)
class UnaryOp:
    op: str  # 'not', '-', '+'
    operand: "ASTNode"


@dataclass(frozen=True)
class BinaryOp:
    op: str  # '=', '!=', '<', '<=', '>', '>=', 'in', 'not in', 'and', 'or', '+', '-', '*', '/'
    left: "ASTNode"
    right: "ASTNode"


@dataclass(frozen=True)
class FunctionCall:
    name: str
    args: Tuple["ASTNode", ...]


ASTNode = Any  # Strukturelle Union; explizit für Lesbarkeit.
