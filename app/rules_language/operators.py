"""Implementierung der Operatoren auf DSL-Werten.

Die DSL nutzt eine eigene Wertedomäne (Python-Objekte plus ``None`` für
``null``). Vergleiche behandeln ``None`` SQL-nah: jeder Vergleich mit
``None`` ergibt ``False`` – außer ``is_null``/``is_not_null`` aus
``functions.py``.

Für Vergleiche zwischen Zahl- und Stringwerten wird versucht, beide auf
Zahlen zu casten; gelingt das nicht, vergleichen wir als (case-insensitive)
String. So bleibt ``c0040 = "ISIN"`` robust gegen unterschiedliche
Ergebnisspalten (object vs. string).
"""

from __future__ import annotations

from typing import Any, Iterable

from app.rules_language.diagnostics import TypeError as DSLTypeError


def _as_number(value: Any):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        if not s:
            return None
        try:
            if "." in s or "e" in s.lower():
                return float(s)
            return int(s)
        except ValueError:
            return None
    return None


def _coerce_for_compare(a: Any, b: Any):
    na, nb = _as_number(a), _as_number(b)
    if na is not None and nb is not None:
        return na, nb
    return _as_string(a), _as_string(b)


def _as_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def op_eq(a: Any, b: Any) -> bool:
    # Konsistente Null-Semantik (siehe docs/PHASE2_DSL_SPEC.md):
    # ``x = null`` und ``null = x`` werden als „ist x null?“ interpretiert.
    # Damit gilt insbesondere ``null = null`` → True und
    # ``"x" = null`` → False symmetrisch.
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    ca, cb = _coerce_for_compare(a, b)
    if isinstance(ca, str) and isinstance(cb, str):
        return ca.casefold() == cb.casefold()
    return ca == cb


def op_neq(a: Any, b: Any) -> bool:
    # Symmetrisches Komplement zu ``op_eq`` inkl. Null-Semantik:
    # ``"x" != null`` → True, ``null != null`` → False.
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return not op_eq(a, b)


def _numeric_compare(a: Any, b: Any, py_op) -> bool:
    if a is None or b is None:
        return False
    na, nb = _as_number(a), _as_number(b)
    if na is None or nb is None:
        # Stringvergleich nur als Fallback bei "<"/">" auf String
        sa, sb = _as_string(a), _as_string(b)
        return py_op(sa, sb)
    return py_op(na, nb)


def op_lt(a: Any, b: Any) -> bool:
    return _numeric_compare(a, b, lambda x, y: x < y)


def op_lte(a: Any, b: Any) -> bool:
    return _numeric_compare(a, b, lambda x, y: x <= y)


def op_gt(a: Any, b: Any) -> bool:
    return _numeric_compare(a, b, lambda x, y: x > y)


def op_gte(a: Any, b: Any) -> bool:
    return _numeric_compare(a, b, lambda x, y: x >= y)


def op_in(value: Any, container: Iterable[Any]) -> bool:
    if value is None:
        return False
    try:
        seq = list(container)
    except TypeError:
        raise DSLTypeError("'in' rechte Seite ist nicht iterierbar")
    return any(op_eq(value, item) for item in seq)


def op_not_in(value: Any, container: Iterable[Any]) -> bool:
    if value is None:
        return False
    return not op_in(value, container)


def op_add(a: Any, b: Any):
    na, nb = _as_number(a), _as_number(b)
    if na is None or nb is None:
        return _as_string(a) + _as_string(b)
    return na + nb


def op_sub(a: Any, b: Any):
    na, nb = _as_number(a), _as_number(b)
    if na is None or nb is None:
        raise DSLTypeError(f"Subtraktion auf nicht-numerischen Werten: {a!r}, {b!r}")
    return na - nb


def op_mul(a: Any, b: Any):
    na, nb = _as_number(a), _as_number(b)
    if na is None or nb is None:
        raise DSLTypeError(f"Multiplikation auf nicht-numerischen Werten: {a!r}, {b!r}")
    return na * nb


def op_div(a: Any, b: Any):
    na, nb = _as_number(a), _as_number(b)
    if na is None or nb is None or nb == 0:
        raise DSLTypeError(f"Division ungültig: {a!r} / {b!r}")
    return na / nb


def to_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)
