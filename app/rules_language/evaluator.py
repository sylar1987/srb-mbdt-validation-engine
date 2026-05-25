"""AST-Evaluator gegen einen Row-/Validation-Kontext."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from app.rules_language import functions, operators
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
from app.rules_language.diagnostics import (
    Diagnostic,
    UnknownFieldError,
    UnknownTemplateError,
)
from app.rules_language.parser import parse


@dataclass
class EvaluationContext:
    """Laufzeit-Kontext für den DSL-Evaluator.

    Im Row-Scope ist ``df`` das aktive Template, ``row_index`` die aktuelle
    Zeile. Cross-Template-Referenzen lösen sich über ``templates`` auf
    (Mapping ``template_id → DataFrame``).
    """

    df: Optional[pd.DataFrame] = None
    row_index: int = 0
    templates: Dict[str, pd.DataFrame] = field(default_factory=dict)
    current_template: str = ""
    diagnostics: List[Diagnostic] = field(default_factory=list)

    def record(self, diag: Diagnostic) -> None:
        self.diagnostics.append(diag)


def _find_column(df: pd.DataFrame, code: str) -> Optional[str]:
    # Lokaler, defensiver Lookup. Findet sowohl "c0040" als auch "c40" /
    # "c0040 - Label" / "C0040" als Header.
    from app.normalization.headers import find_column

    return find_column(df, code)


def _read_field(ctx: EvaluationContext, field_code: str, template: str) -> Any:
    df: Optional[pd.DataFrame] = None
    if template:
        df = ctx.templates.get(template)
        if df is None:
            # Versuche fuzzy-Lookup über find_matching_keys
            from app.services.template_lookup_service import find_matching_keys

            matching = find_matching_keys(ctx.templates, template) if ctx.templates else []
            if matching:
                df = ctx.templates[matching[0]]
        if df is None:
            raise UnknownTemplateError(template)
    else:
        df = ctx.df

    if df is None:
        raise UnknownTemplateError(template or ctx.current_template or "<row>")

    col = _find_column(df, field_code)
    if col is None:
        raise UnknownFieldError(field_code, template or ctx.current_template)

    if template:
        # Cross-Template: erste passende Zeile bzw. die durch row_index
        # adressierte Zeile, falls vorhanden. Wir nutzen row_index nur, wenn
        # das Ziel-DataFrame ihn deckt; sonst die erste Zeile (typischer
        # Header/Single-Row-Lookup).
        idx = ctx.row_index if ctx.row_index < len(df) else 0
        if idx >= len(df):
            return None
        return _normalize(df[col].iloc[idx])

    if ctx.row_index >= len(df):
        return None
    return _normalize(df[col].iloc[ctx.row_index])


def _normalize(value: Any) -> Any:
    """Wandelt pandas-/numpy-typische Sonderwerte in Pythonwerte um."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


def _evaluate(node: ASTNode, ctx: EvaluationContext) -> Any:
    if isinstance(node, NumberLiteral):
        return node.value
    if isinstance(node, StringLiteral):
        return node.value
    if isinstance(node, BoolLiteral):
        return node.value
    if isinstance(node, NullLiteral):
        return None
    if isinstance(node, FieldRef):
        return _read_field(ctx, node.field_code, node.template)
    if isinstance(node, TemplateRef):
        df = ctx.templates.get(node.template)
        if df is None:
            raise UnknownTemplateError(node.template)
        return df
    if isinstance(node, ListExpr):
        return [_evaluate(item, ctx) for item in node.items]
    if isinstance(node, UnaryOp):
        val = _evaluate(node.operand, ctx)
        if node.op == "not":
            return not operators.to_bool(val)
        if node.op == "-":
            n = operators._as_number(val)  # type: ignore[attr-defined]
            if n is None:
                from app.rules_language.diagnostics import TypeError as DSLTypeError
                raise DSLTypeError(f"Unäres - auf nicht-numerischem Wert: {val!r}")
            return -n
        if node.op == "+":
            return val
        raise AssertionError(f"unbekannter unärer Operator {node.op}")
    if isinstance(node, BinaryOp):
        return _eval_binary(node, ctx)
    if isinstance(node, FunctionCall):
        args = [_evaluate(a, ctx) for a in node.args]
        return functions.call(node.name, args)
    raise AssertionError(f"Unbekannter AST-Knoten: {type(node).__name__}")


def _eval_binary(node: BinaryOp, ctx: EvaluationContext) -> Any:
    op = node.op
    # Kurzschluss-Auswertung für and/or
    if op == "and":
        left = operators.to_bool(_evaluate(node.left, ctx))
        if not left:
            return False
        return operators.to_bool(_evaluate(node.right, ctx))
    if op == "or":
        left = operators.to_bool(_evaluate(node.left, ctx))
        if left:
            return True
        return operators.to_bool(_evaluate(node.right, ctx))

    left = _evaluate(node.left, ctx)
    right = _evaluate(node.right, ctx)

    if op == "=" or op == "==":
        return operators.op_eq(left, right)
    if op == "!=" or op == "<>":
        return operators.op_neq(left, right)
    if op == "<":
        return operators.op_lt(left, right)
    if op == "<=":
        return operators.op_lte(left, right)
    if op == ">":
        return operators.op_gt(left, right)
    if op == ">=":
        return operators.op_gte(left, right)
    if op == "in":
        return operators.op_in(left, right if isinstance(right, list) else [right])
    if op == "not in":
        return operators.op_not_in(left, right if isinstance(right, list) else [right])
    if op == "+":
        return operators.op_add(left, right)
    if op == "-":
        return operators.op_sub(left, right)
    if op == "*":
        return operators.op_mul(left, right)
    if op == "/":
        return operators.op_div(left, right)

    raise AssertionError(f"unbekannter binärer Operator {op}")


def evaluate(source_or_ast: Any, ctx: EvaluationContext) -> Any:
    """Wertet einen DSL-Ausdruck oder AST gegen ``ctx`` aus."""
    if isinstance(source_or_ast, str):
        node = parse(source_or_ast)
    else:
        node = source_or_ast
    return _evaluate(node, ctx)
