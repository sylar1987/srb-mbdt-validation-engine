"""Recursive-Descent-Parser für die DSL.

Operatorpräzedenz – höchste zuerst, siehe ``docs/PHASE2_DSL_SPEC.md``:

  1. Primäre Ausdrücke (Literale, Bezeichner, Funktionsaufrufe, Klammern)
  2. Unär: ``not``, unäres ``-``/``+``
  3. Multiplikativ: ``*``, ``/``
  4. Additiv: ``+``, ``-``
  5. Vergleich: ``=``/``==``, ``!=``/``<>``, ``<``, ``<=``, ``>``, ``>=``
  6. Membership: ``in``, ``not in``
  7. ``and``
  8. ``or``
"""

from __future__ import annotations

import re
from typing import List

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
from app.rules_language.diagnostics import SyntaxError as DSLSyntaxError
from app.rules_language.lexer import tokenize
from app.rules_language.tokens import Token, TokenType


_FIELD_RE = re.compile(r"^c\d{1,4}$", re.IGNORECASE)
_TEMPLATE_RE = re.compile(r"^[A-Za-z]\d+(?:\.\d+)?$")
_CROSS_RE = re.compile(r"^([A-Za-z]\d+(?:\.\d+)?)\.(c\d{1,4})$", re.IGNORECASE)


class _Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    @property
    def cur(self) -> Token:
        return self.tokens[self.pos]

    def eat(self, kind: TokenType) -> Token:
        t = self.cur
        if t.type != kind:
            raise DSLSyntaxError(
                f"Expected {kind.value}, got {t.type.value}", t.pos
            )
        self.pos += 1
        return t

    def match(self, *kinds: TokenType) -> bool:
        if self.cur.type in kinds:
            self.pos += 1
            return True
        return False

    # ---- Grammatik --------------------------------------------------

    def parse(self) -> ASTNode:
        node = self.parse_or()
        if self.cur.type != TokenType.EOF:
            raise DSLSyntaxError(
                f"Unexpected token {self.cur.type.value}", self.cur.pos
            )
        return node

    def parse_or(self) -> ASTNode:
        left = self.parse_and()
        while self.cur.type == TokenType.OR:
            self.pos += 1
            right = self.parse_and()
            left = BinaryOp("or", left, right)
        return left

    def parse_and(self) -> ASTNode:
        left = self.parse_not()
        while self.cur.type == TokenType.AND:
            self.pos += 1
            right = self.parse_not()
            left = BinaryOp("and", left, right)
        return left

    def parse_not(self) -> ASTNode:
        if self.cur.type == TokenType.NOT:
            self.pos += 1
            return UnaryOp("not", self.parse_not())
        return self.parse_membership()

    def parse_membership(self) -> ASTNode:
        left = self.parse_comparison()
        while self.cur.type in (TokenType.IN, TokenType.NOT_IN):
            op = "in" if self.cur.type == TokenType.IN else "not in"
            self.pos += 1
            right = self.parse_comparison()
            left = BinaryOp(op, left, right)
        return left

    def parse_comparison(self) -> ASTNode:
        left = self.parse_additive()
        cmp_ops = {
            TokenType.EQ: "=",
            TokenType.NEQ: "!=",
            TokenType.LT: "<",
            TokenType.LTE: "<=",
            TokenType.GT: ">",
            TokenType.GTE: ">=",
        }
        if self.cur.type in cmp_ops:
            op = cmp_ops[self.cur.type]
            self.pos += 1
            right = self.parse_additive()
            return BinaryOp(op, left, right)
        return left

    def parse_additive(self) -> ASTNode:
        left = self.parse_multiplicative()
        while self.cur.type in (TokenType.PLUS, TokenType.MINUS):
            op = "+" if self.cur.type == TokenType.PLUS else "-"
            self.pos += 1
            right = self.parse_multiplicative()
            left = BinaryOp(op, left, right)
        return left

    def parse_multiplicative(self) -> ASTNode:
        left = self.parse_unary()
        while self.cur.type in (TokenType.STAR, TokenType.SLASH):
            op = "*" if self.cur.type == TokenType.STAR else "/"
            self.pos += 1
            right = self.parse_unary()
            left = BinaryOp(op, left, right)
        return left

    def parse_unary(self) -> ASTNode:
        if self.cur.type == TokenType.MINUS:
            self.pos += 1
            return UnaryOp("-", self.parse_unary())
        if self.cur.type == TokenType.PLUS:
            self.pos += 1
            return UnaryOp("+", self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        t = self.cur
        if t.type == TokenType.NUMBER:
            self.pos += 1
            return NumberLiteral(t.value)
        if t.type == TokenType.STRING:
            self.pos += 1
            return StringLiteral(t.value)
        if t.type == TokenType.BOOL:
            self.pos += 1
            return BoolLiteral(t.value)
        if t.type == TokenType.NULL:
            self.pos += 1
            return NullLiteral()
        if t.type == TokenType.LPAREN:
            return self.parse_paren_or_list()
        if t.type == TokenType.LBRACK:
            return self.parse_bracket_list()
        if t.type == TokenType.IDENT:
            return self.parse_ident()
        raise DSLSyntaxError(f"Unexpected token {t.type.value}", t.pos)

    def parse_paren_or_list(self) -> ASTNode:
        # Klammer kann entweder Gruppierung oder Liste sein.
        self.eat(TokenType.LPAREN)
        if self.cur.type == TokenType.RPAREN:
            self.pos += 1
            return ListExpr(items=tuple())
        first = self.parse_or()
        if self.cur.type == TokenType.COMMA:
            items: List[ASTNode] = [first]
            while self.match(TokenType.COMMA):
                items.append(self.parse_or())
            self.eat(TokenType.RPAREN)
            return ListExpr(items=tuple(items))
        self.eat(TokenType.RPAREN)
        return first

    def parse_bracket_list(self) -> ASTNode:
        self.eat(TokenType.LBRACK)
        items: List[ASTNode] = []
        if self.cur.type != TokenType.RBRACK:
            items.append(self.parse_or())
            while self.match(TokenType.COMMA):
                items.append(self.parse_or())
        self.eat(TokenType.RBRACK)
        return ListExpr(items=tuple(items))

    def parse_ident(self) -> ASTNode:
        t = self.eat(TokenType.IDENT)
        name = t.value
        # Funktionsaufruf? – Klammer direkt dahinter.
        if self.cur.type == TokenType.LPAREN:
            self.pos += 1
            args: List[ASTNode] = []
            if self.cur.type != TokenType.RPAREN:
                args.append(self.parse_or())
                while self.match(TokenType.COMMA):
                    args.append(self.parse_or())
            self.eat(TokenType.RPAREN)
            return FunctionCall(name=name.lower(), args=tuple(args))

        cross = _CROSS_RE.match(name)
        if cross:
            return FieldRef(
                field_code=cross.group(2).lower(),
                template=cross.group(1),
            )
        if _FIELD_RE.match(name):
            return FieldRef(field_code=name.lower(), template="")
        if _TEMPLATE_RE.match(name):
            return TemplateRef(template=name)

        # Fallback: behandle als reines Feld – Diagnose erfolgt im Evaluator.
        return FieldRef(field_code=name.lower(), template="")


def parse(source: str) -> ASTNode:
    """Parst einen DSL-Ausdruck zu einem AST-Knoten."""
    tokens = tokenize(source)
    return _Parser(tokens).parse()
