"""Built-in-Funktionen der DSL.

Funktionen werden im Evaluator über ``BUILT_INS`` aufgelöst. Unbekannte
Funktionen liefern ``UnsupportedFunctionError``.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, Sequence

from app.rules_language.diagnostics import (
    TypeError as DSLTypeError,
    UnsupportedFunctionError,
)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def fn_is_null(args: Sequence[Any]) -> bool:
    if len(args) != 1:
        raise DSLTypeError(f"is_null erwartet 1 Argument, bekam {len(args)}")
    return _is_missing(args[0])


def fn_is_not_null(args: Sequence[Any]) -> bool:
    if len(args) != 1:
        raise DSLTypeError(f"is_not_null erwartet 1 Argument, bekam {len(args)}")
    return not _is_missing(args[0])


def fn_is_reported(args: Sequence[Any]) -> bool:
    if len(args) != 1:
        raise DSLTypeError(f"is_reported erwartet 1 Argument, bekam {len(args)}")
    value = args[0]
    if _is_missing(value):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


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
            return float(s) if ("." in s or "e" in s.lower()) else int(s)
        except ValueError:
            return None
    return None


def fn_abs(args: Sequence[Any]):
    if len(args) != 1:
        raise DSLTypeError(f"abs erwartet 1 Argument, bekam {len(args)}")
    n = _as_number(args[0])
    if n is None:
        raise DSLTypeError(f"abs erfordert eine Zahl, bekam {args[0]!r}")
    return abs(n)


def fn_min(args: Sequence[Any]):
    nums = [_as_number(a) for a in args]
    if not nums or any(n is None for n in nums):
        raise DSLTypeError("min erfordert ≥1 numerische Argumente")
    return min(nums)


def fn_max(args: Sequence[Any]):
    nums = [_as_number(a) for a in args]
    if not nums or any(n is None for n in nums):
        raise DSLTypeError("max erfordert ≥1 numerische Argumente")
    return max(nums)


def fn_len(args: Sequence[Any]):
    if len(args) != 1:
        raise DSLTypeError(f"len erwartet 1 Argument, bekam {len(args)}")
    v = args[0]
    if v is None:
        return 0
    return len(str(v))


def fn_lower(args: Sequence[Any]):
    if len(args) != 1:
        raise DSLTypeError(f"lower erwartet 1 Argument, bekam {len(args)}")
    v = args[0]
    return "" if v is None else str(v).lower()


def fn_upper(args: Sequence[Any]):
    if len(args) != 1:
        raise DSLTypeError(f"upper erwartet 1 Argument, bekam {len(args)}")
    v = args[0]
    return "" if v is None else str(v).upper()


BUILT_INS: Dict[str, Callable[[Sequence[Any]], Any]] = {
    "is_null": fn_is_null,
    "is_not_null": fn_is_not_null,
    "is_reported": fn_is_reported,
    "abs": fn_abs,
    "min": fn_min,
    "max": fn_max,
    "len": fn_len,
    "lower": fn_lower,
    "upper": fn_upper,
}


def call(name: str, args: Sequence[Any]) -> Any:
    fn = BUILT_INS.get(name.lower())
    if fn is None:
        raise UnsupportedFunctionError(name)
    return fn(args)
