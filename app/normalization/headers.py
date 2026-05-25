"""Header-/Spaltenname-Normalisierung."""

from __future__ import annotations

from typing import List, Optional

from app.normalization.field_resolver import extract_field_code_from_header
from app.utils.regex_patterns import (
    FIELD_CODE_4DIGIT,
    FIELD_CODE_C_PREFIX,
    FIELD_CODE_SHORT_DIGIT,
)


def normalize_col_names(cols: List[str]) -> List[str]:
    """Normalisiert Spaltennamen zu ``cXXXX`` und dedupliziert.

    Unterstützt sowohl reine technische DPM-Bezeichnungen (``c0040``,
    ``0040``, ``40``) als auch kombinierte Header (``c0040 - Caption``,
    ``c0040 (Caption)``, ``0040: Caption`` u. a.). Reine Captions bleiben
    unverändert; ihr Mapping erfolgt erst über
    :func:`app.normalization.field_resolver.resolve_dataframe_columns`,
    da hierfür Template-Kontext (``field_structure.json``) benötigt wird.
    """
    normalized: List[str] = []
    seen: dict[str, int] = {}
    for col in cols:
        col_str = str(col).strip()
        if FIELD_CODE_4DIGIT.match(col_str):
            name = f"c{col_str}"
        elif FIELD_CODE_C_PREFIX.match(col_str):
            name = col_str.lower()
        elif FIELD_CODE_SHORT_DIGIT.match(col_str):
            name = f"c{col_str.zfill(4)}"
        else:
            code, _caption = extract_field_code_from_header(col_str)
            name = code if code else col_str
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        normalized.append(name)
    return normalized


def find_header_row(all_rows: list) -> Optional[int]:
    """Findet die Zeile mit 4-stelligen Spaltencodes (auch Integer-Codes)."""
    for idx, row in enumerate(all_rows):
        count = 0
        for c in row:
            if c is None:
                continue
            cs = str(c).strip()
            if cs.isdigit() and 10 <= int(cs) <= 9999:
                count += 1
            elif cs.zfill(4).isdigit() and len(cs) == 4:
                count += 1
        if count >= 2:
            return idx
    return None


def extract_headers(all_rows: list, code_row_idx: int) -> List[str]:
    """Extrahiert Spaltennamen aus der Code-Zeile inkl. Dedup."""
    code_row = all_rows[code_row_idx]
    label_row = all_rows[code_row_idx - 1] if code_row_idx > 0 else []
    headers: List[str] = []
    seen: dict[str, int] = {}

    for i, code in enumerate(code_row):
        if code is not None:
            code_str = str(code).strip()
            if code_str.isdigit():
                col_name = f"c{code_str.zfill(4)}"
            else:
                extracted, _caption = extract_field_code_from_header(code_str)
                col_name = extracted if extracted else code_str
        else:
            label = label_row[i] if i < len(label_row) else None
            if label and str(label).strip():
                col_name = str(label).strip()[:40].replace(" ", "_")
            else:
                col_name = f"col_{i}"

        if col_name in seen:
            seen[col_name] += 1
            col_name = f"{col_name}_{seen[col_name]}"
        else:
            seen[col_name] = 0
        headers.append(col_name)

    return headers


def find_column(df, field_code: str) -> Optional[str]:
    """Sucht eine Spalte im DataFrame mit flexiblem Matching (cXXXX ↔ XXXX)."""
    if df is None or not field_code:
        return None
    if field_code in df.columns:
        return field_code
    alt = field_code[1:] if field_code.startswith("c") else f"c{field_code}"
    if alt in df.columns:
        return alt
    normalized = f"c{field_code.lstrip('c').zfill(4)}"
    if normalized in df.columns:
        return normalized
    return None
