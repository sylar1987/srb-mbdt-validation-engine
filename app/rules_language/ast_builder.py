"""Helfer zum Bauen von ASTs aus Code – primär für Tests.

In Phase 2 erfolgt das AST-Building direkt im ``parser.py``. Dieses Modul
bietet kleine Convenience-Helper für Testfixtures und für spätere
DPM-Importer (Phase 3), die Regeln nicht über den DSL-Parser, sondern
programmatisch erzeugen wollen.
"""

from __future__ import annotations

from typing import Iterable

from app.rules_language.ast_nodes import (
    ASTNode,
    BinaryOp,
    BoolLiteral,
    FieldRef,
    FunctionCall,
    ListExpr,
    NullLiteral,
    NumberLiteral,
    StringLiteral,
    UnaryOp,
)


def field(code: str, template: str = "") -> FieldRef:
    return FieldRef(field_code=code.lower(), template=template)


def num(value) -> NumberLiteral:
    return NumberLiteral(value=value)


def s(value: str) -> StringLiteral:
    return StringLiteral(value=value)


def b(value: bool) -> BoolLiteral:
    return BoolLiteral(value=value)


def null_() -> NullLiteral:
    return NullLiteral()


def binop(op: str, left: ASTNode, right: ASTNode) -> BinaryOp:
    return BinaryOp(op=op, left=left, right=right)


def unop(op: str, operand: ASTNode) -> UnaryOp:
    return UnaryOp(op=op, operand=operand)


def call(name: str, *args: ASTNode) -> FunctionCall:
    return FunctionCall(name=name.lower(), args=tuple(args))


def lst(items: Iterable[ASTNode]) -> ListExpr:
    return ListExpr(items=tuple(items))
