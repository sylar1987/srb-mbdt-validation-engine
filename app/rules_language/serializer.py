"""Serialisierung von AST-Knoten in eine deterministische Form.

Wird für Tests, Debugging und spätere Audit-Trails verwendet.
"""

from __future__ import annotations

from typing import Any, Dict

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
    TemplateRef,
    UnaryOp,
)


def serialize(node: ASTNode) -> Dict[str, Any]:
    if isinstance(node, NumberLiteral):
        return {"type": "Number", "value": node.value}
    if isinstance(node, StringLiteral):
        return {"type": "String", "value": node.value}
    if isinstance(node, BoolLiteral):
        return {"type": "Bool", "value": node.value}
    if isinstance(node, NullLiteral):
        return {"type": "Null"}
    if isinstance(node, FieldRef):
        return {
            "type": "FieldRef",
            "field": node.field_code,
            "template": node.template,
        }
    if isinstance(node, TemplateRef):
        return {"type": "TemplateRef", "template": node.template}
    if isinstance(node, ListExpr):
        return {"type": "List", "items": [serialize(i) for i in node.items]}
    if isinstance(node, UnaryOp):
        return {"type": "Unary", "op": node.op, "operand": serialize(node.operand)}
    if isinstance(node, BinaryOp):
        return {
            "type": "Binary",
            "op": node.op,
            "left": serialize(node.left),
            "right": serialize(node.right),
        }
    if isinstance(node, FunctionCall):
        return {
            "type": "Call",
            "name": node.name,
            "args": [serialize(a) for a in node.args],
        }
    raise AssertionError(f"Cannot serialize {type(node).__name__}")
