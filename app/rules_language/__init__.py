"""Phase-2-Regel-DSL: Lexer, Parser, AST, Evaluator.

Öffentliche API:

- ``parse(text)`` → AST-Knoten
- ``evaluate(text, context)`` → ausgewerteter Wert / Wahrheitswert
- ``Diagnostic`` / ``DSLError`` für Fehlerbehandlung
- ``EvaluationContext`` als Datenträger für den Evaluator

Detaillierte Spezifikation: ``docs/PHASE2_DSL_SPEC.md``.
"""

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
    DSLError,
    Diagnostic,
    DiagnosticCode,
    SyntaxError as DSLSyntaxError,
    UnsupportedFunctionError,
)
from app.rules_language.evaluator import EvaluationContext, evaluate
from app.rules_language.parser import parse
from app.rules_language.serializer import serialize


__all__ = [
    "ASTNode",
    "BinaryOp",
    "BoolLiteral",
    "FieldRef",
    "FunctionCall",
    "ListExpr",
    "NullLiteral",
    "NumberLiteral",
    "StringLiteral",
    "TemplateRef",
    "UnaryOp",
    "Diagnostic",
    "DiagnosticCode",
    "DSLError",
    "DSLSyntaxError",
    "UnsupportedFunctionError",
    "EvaluationContext",
    "evaluate",
    "parse",
    "serialize",
]
