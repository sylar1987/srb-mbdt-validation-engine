"""Lexer- und Parser-Tests für die DSL (Phase 2)."""

import pytest

from app.rules_language import parse, serialize
from app.rules_language.ast_nodes import (
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
from app.rules_language.diagnostics import DSLError
from app.rules_language.lexer import tokenize
from app.rules_language.tokens import TokenType


def test_tokenize_simple_equality():
    toks = tokenize('c0040 = "ISIN"')
    types = [t.type for t in toks]
    assert types == [TokenType.IDENT, TokenType.EQ, TokenType.STRING, TokenType.EOF]


def test_tokenize_operators():
    toks = tokenize('c0040 != "x" and c0050 >= 1.5 or not c0060 in (1,2)')
    kinds = [t.type for t in toks]
    assert TokenType.NEQ in kinds
    assert TokenType.GTE in kinds
    assert TokenType.AND in kinds
    assert TokenType.OR in kinds
    assert TokenType.NOT in kinds
    assert TokenType.IN in kinds


def test_tokenize_not_in_merge():
    toks = tokenize('c0040 not in ("a","b")')
    assert any(t.type == TokenType.NOT_IN for t in toks)
    assert not any(t.type == TokenType.NOT for t in toks)


def test_tokenize_string_escapes():
    toks = tokenize(r'"a \"b\" c"')
    assert toks[0].value == 'a "b" c'


def test_tokenize_unterminated_string():
    with pytest.raises(DSLError):
        tokenize('"abc')


def test_parse_field_equality():
    ast = parse('c0040 = "ISIN"')
    assert isinstance(ast, BinaryOp)
    assert ast.op == "="
    assert isinstance(ast.left, FieldRef)
    assert ast.left.field_code == "c0040"
    assert isinstance(ast.right, StringLiteral)
    assert ast.right.value == "ISIN"


def test_parse_membership():
    ast = parse('c0250 in ("Structured", "Only structured coupon")')
    assert isinstance(ast, BinaryOp)
    assert ast.op == "in"
    assert isinstance(ast.right, ListExpr)
    assert len(ast.right.items) == 2


def test_parse_not_in():
    ast = parse('c0250 not in ("A","B")')
    assert isinstance(ast, BinaryOp)
    assert ast.op == "not in"


def test_parse_and_or_precedence():
    ast = parse('a = 1 or b = 2 and c = 3')
    assert ast.op == "or"
    # `and` bindet stärker als `or`
    assert ast.right.op == "and"


def test_parse_unary_not():
    ast = parse('not c0040 = "ISIN"')
    assert isinstance(ast, UnaryOp)
    assert ast.op == "not"


def test_parse_function_call():
    ast = parse('is_not_null(c0070)')
    assert isinstance(ast, FunctionCall)
    assert ast.name == "is_not_null"
    assert isinstance(ast.args[0], FieldRef)


def test_parse_cross_template_ref():
    ast = parse('B02.00.c0040 = c0040')
    assert isinstance(ast.left, FieldRef)
    assert ast.left.template == "B02.00"
    assert ast.left.field_code == "c0040"


def test_parse_paren_grouping_not_a_list():
    ast = parse('(c0040 = "ISIN")')
    assert isinstance(ast, BinaryOp)


def test_parse_syntax_error_unbalanced():
    with pytest.raises(DSLError):
        parse('(c0040 = "ISIN"')


def test_parse_syntax_error_dangling():
    with pytest.raises(DSLError):
        parse('c0040 =')


def test_serialize_roundtrip_shape():
    ast = parse('c0040 = "ISIN" and is_not_null(c0050)')
    data = serialize(ast)
    assert data["type"] == "Binary"
    assert data["op"] == "and"
    assert data["right"]["type"] == "Call"


def test_parse_booleans_and_null():
    ast = parse('true')
    assert isinstance(ast, BoolLiteral) and ast.value is True
    ast = parse('false')
    assert isinstance(ast, BoolLiteral) and ast.value is False
    ast = parse('null')
    assert isinstance(ast, NullLiteral)


def test_parse_number_literals():
    ast = parse('-1.5 + 2')
    assert ast.op == "+"
    assert isinstance(ast.left, UnaryOp)
    assert isinstance(ast.left.operand, NumberLiteral)
    assert ast.left.operand.value == 1.5
    assert isinstance(ast.right, NumberLiteral)
    assert ast.right.value == 2
