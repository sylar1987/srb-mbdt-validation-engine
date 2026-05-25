"""Lexer für die DSL.

Erzeugt eine flache Tokenliste. Whitespace wird ignoriert. Strings werden
mit ``"`` oder ``'`` umschlossen und unterstützen einfaches Escaping
(``\\"``, ``\\'``, ``\\\\``).
"""

from __future__ import annotations

from typing import List

from app.rules_language.diagnostics import SyntaxError as DSLSyntaxError
from app.rules_language.tokens import Token, TokenType


_KEYWORDS = {
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "in": TokenType.IN,
    "true": TokenType.BOOL,
    "false": TokenType.BOOL,
    "null": TokenType.NULL,
}


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    n = len(source)

    while i < n:
        ch = source[i]

        if ch.isspace():
            i += 1
            continue

        if ch in "(){}[],":
            mapping = {
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "[": TokenType.LBRACK,
                "]": TokenType.RBRACK,
                ",": TokenType.COMMA,
            }
            if ch in mapping:
                tokens.append(Token(mapping[ch], ch, i))
                i += 1
                continue

        if ch == "=":
            if i + 1 < n and source[i + 1] == "=":
                tokens.append(Token(TokenType.EQ, "==", i))
                i += 2
            else:
                tokens.append(Token(TokenType.EQ, "=", i))
                i += 1
            continue

        if ch == "!":
            if i + 1 < n and source[i + 1] == "=":
                tokens.append(Token(TokenType.NEQ, "!=", i))
                i += 2
                continue
            raise DSLSyntaxError("Unexpected character '!'", i)

        if ch == "<":
            if i + 1 < n and source[i + 1] == ">":
                tokens.append(Token(TokenType.NEQ, "<>", i))
                i += 2
            elif i + 1 < n and source[i + 1] == "=":
                tokens.append(Token(TokenType.LTE, "<=", i))
                i += 2
            else:
                tokens.append(Token(TokenType.LT, "<", i))
                i += 1
            continue

        if ch == ">":
            if i + 1 < n and source[i + 1] == "=":
                tokens.append(Token(TokenType.GTE, ">=", i))
                i += 2
            else:
                tokens.append(Token(TokenType.GT, ">", i))
                i += 1
            continue

        if ch == "+":
            tokens.append(Token(TokenType.PLUS, "+", i))
            i += 1
            continue
        if ch == "-":
            tokens.append(Token(TokenType.MINUS, "-", i))
            i += 1
            continue
        if ch == "*":
            tokens.append(Token(TokenType.STAR, "*", i))
            i += 1
            continue
        if ch == "/":
            tokens.append(Token(TokenType.SLASH, "/", i))
            i += 1
            continue

        if ch in ('"', "'"):
            value, j = _read_string(source, i, ch)
            tokens.append(Token(TokenType.STRING, value, i))
            i = j
            continue

        if ch.isdigit():
            value, j = _read_number(source, i)
            tokens.append(Token(TokenType.NUMBER, value, i))
            i = j
            continue

        if _ident_start(ch):
            value, j = _read_identifier(source, i)
            lower = value.lower()
            if lower in _KEYWORDS:
                kind = _KEYWORDS[lower]
                if kind == TokenType.BOOL:
                    tokens.append(Token(kind, lower == "true", i))
                elif kind == TokenType.NULL:
                    tokens.append(Token(kind, None, i))
                else:
                    tokens.append(Token(kind, lower, i))
            else:
                tokens.append(Token(TokenType.IDENT, value, i))
            i = j
            continue

        raise DSLSyntaxError(f"Unexpected character {ch!r}", i)

    tokens.append(Token(TokenType.EOF, None, n))
    return _merge_not_in(tokens)


def _merge_not_in(tokens: List[Token]) -> List[Token]:
    """Verschmilzt ``NOT`` + ``IN`` zu einem ``NOT_IN``-Token."""
    merged: List[Token] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if (
            t.type == TokenType.NOT
            and i + 1 < len(tokens)
            and tokens[i + 1].type == TokenType.IN
        ):
            merged.append(Token(TokenType.NOT_IN, "not in", t.pos))
            i += 2
        else:
            merged.append(t)
            i += 1
    return merged


def _read_string(source: str, start: int, quote: str):
    i = start + 1
    n = len(source)
    out: List[str] = []
    while i < n:
        ch = source[i]
        if ch == "\\" and i + 1 < n:
            nxt = source[i + 1]
            out.append(nxt)
            i += 2
            continue
        if ch == quote:
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    raise DSLSyntaxError("Unterminated string literal", start)


def _read_number(source: str, start: int):
    i = start
    n = len(source)
    has_dot = False
    while i < n:
        ch = source[i]
        if ch.isdigit():
            i += 1
            continue
        if ch == "." and not has_dot:
            if i + 1 < n and source[i + 1].isdigit():
                has_dot = True
                i += 1
                continue
            break
        break
    text = source[start:i]
    return (float(text) if has_dot else int(text)), i


def _ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _ident_part(ch: str) -> bool:
    return ch.isalnum() or ch in ("_", ".")


def _read_identifier(source: str, start: int):
    i = start
    n = len(source)
    while i < n and _ident_part(source[i]):
        i += 1
    return source[start:i], i
