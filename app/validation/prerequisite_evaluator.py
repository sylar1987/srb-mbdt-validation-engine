"""Phase-1-Prerequisite-Evaluator – Einstiegspunkt für die spätere AST-Engine.

Aktuell deckt dieses Modul exakt die Muster ab, die ``MBDTValidator
._check_prerequisite`` heute kennt: einfache Gleichheit, Stichwörter
``structured``/``non-structured``. Komplexere Ausdrücke (verschachteltes
``AND``/``OR``, Vergleichsoperatoren, Cross-Template-Referenzen) sind
explizit Nicht-Ziel für Phase 1 – Phase 2 ersetzt diesen Evaluator durch
einen vollständigen DSL/AST-Parser.
"""

from __future__ import annotations

import re
from typing import Any, Dict

import pandas as pd

from app.normalization.headers import find_column


def evaluate(
    df: pd.DataFrame, row_idx: int, prerequisite: str, rule: Dict[str, Any]
) -> bool:
    """Gibt ``True`` zurück, wenn die Regel auf dieser Zeile angewendet werden soll."""
    if not prerequisite:
        return True

    prereq_lower = prerequisite.lower()

    field_match = re.search(
        r"c(\d{4})\s*=\s*['\"]?([^'\"]+)['\"]?", prerequisite, re.IGNORECASE
    )
    if field_match:
        cond_col_code = f"c{field_match.group(1).zfill(4)}"
        cond_val = field_match.group(2).strip()
        actual_col = find_column(df, cond_col_code)
        if actual_col and row_idx < len(df):
            actual_val = str(df[actual_col].iloc[row_idx]).strip()
            return cond_val.lower() in actual_val.lower()
        return False

    if "non-structured" in prereq_lower:
        col = find_column(df, "c0250")
        if col and row_idx < len(df):
            return "non-structured" in str(df[col].iloc[row_idx]).lower()

    if "structured" in prereq_lower and "non-structured" not in prereq_lower:
        col = find_column(df, "c0250")
        if col and row_idx < len(df):
            v = str(df[col].iloc[row_idx]).lower()
            return "structured" in v and "non-structured" not in v

    return True


# Bewusste Nicht-Ziele in Phase 1 (für Phase 2):
UNSUPPORTED_PATTERNS_DOC = """
Nicht abgedeckt in Phase 1 (Phase 2 / AST-Engine):
  - Verschachtelte Boolesche Ausdrücke (AND/OR/NOT mit Klammern)
  - Vergleichsoperatoren !=, >, <, >=, <=
  - Cross-Template-Referenzen (template.X.cYYYY)
  - Mengenoperatoren (in / not in)
  - Funktionsaufrufe is_null, is_not_null, is_reported
"""
