"""Tokendefinitionen für den DSL-Lexer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TokenType(str, Enum):
    # Literale
    NUMBER = "NUMBER"
    STRING = "STRING"
    BOOL = "BOOL"
    NULL = "NULL"
    # Bezeichner
    IDENT = "IDENT"  # c0040, B02.00, B02.00.c0040
    # Operatoren
    EQ = "EQ"           # =, ==
    NEQ = "NEQ"         # !=, <>
    LT = "LT"           # <
    LTE = "LTE"         # <=
    GT = "GT"           # >
    GTE = "GTE"         # >=
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    IN = "IN"
    NOT_IN = "NOT_IN"
    # Strukturzeichen
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACK = "LBRACK"
    RBRACK = "RBRACK"
    COMMA = "COMMA"
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: Any
    pos: int  # Index im Quelltext

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Token({self.type.value}, {self.value!r}, @{self.pos})"
