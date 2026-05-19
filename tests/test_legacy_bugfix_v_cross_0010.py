"""Regressionstests für den Legacy-Bugfix in v_CROSS_0010.

Hintergrund
-----------
``MBDTValidator._validate_cross_template_rule`` enthielt für
``v_CROSS_0010`` den Ausdruck

    df02_a = self.templates.get("B02.00_TypeA") or self.templates.get("B02.00")

Das löste einen ``ValueError: The truth value of a DataFrame is ambiguous``
aus, sobald der erste ``get`` ein ``DataFrame`` zurücklieferte. Damit
crashte die Regel jedes Mal, wenn ``B02.00_TypeA`` geladen war – also im
SRB-Normalfall.

Dieser Test deckt die drei relevanten Konstellationen ab:
  1. Nur ``B02.00_TypeA`` vorhanden → Regel darf nicht crashen,
     ohne TypeB findet sie nichts.
  2. ``B02.00_TypeA`` und ``B02.00_TypeB`` mit Duplikat → genau ein
     Duplikatsbefund.
  3. ``B02.00_TypeA`` und ``B02.00_TypeB`` ohne Überschneidung → kein Befund.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mbdt_validator import MBDTValidator


def _b99_with_refdate() -> pd.DataFrame:
    return pd.DataFrame({"c0010": ["Bank AG"], "c0070": ["2024-12-31"]})


def _b02_typea(ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"c0010": [str(i) for i in range(1, len(ids) + 1)],
                         "c0020": ids})


def _b02_typeb(ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"c0010": [str(i) for i in range(1, len(ids) + 1)],
                         "c0020": ids})


def _run_only_v_cross_0010(validator: MBDTValidator) -> list[dict]:
    """Führt nur die Regel ``v_CROSS_0010`` aus und liefert ihre Befunde."""
    rule = next(r for r in validator.rules if r.get("rule_id") == "v_CROSS_0010")
    validator.errors = []
    validator._validate_cross_template_rule(rule)
    return [e for e in validator.errors if e["rule_id"] == "v_CROSS_0010"]


def test_v_cross_0010_only_typea_does_not_crash():
    """Mit nur TypeA (ohne TypeB) muss die Regel sauber leer zurückkehren.

    Vorher: ``ValueError: The truth value of a DataFrame is ambiguous.``
    """
    v = MBDTValidator()
    v.templates = {
        "B99.00": _b99_with_refdate(),
        "B02.00_TypeA": _b02_typea(["ID-1", "ID-2"]),
    }
    # Darf nicht werfen
    errs = _run_only_v_cross_0010(v)
    assert errs == []


def test_v_cross_0010_typea_and_typeb_no_overlap():
    """Ohne überlappende IDs gibt es keinen Befund."""
    v = MBDTValidator()
    v.templates = {
        "B99.00": _b99_with_refdate(),
        "B02.00_TypeA": _b02_typea(["ID-1", "ID-2"]),
        "B02.00_TypeB": _b02_typeb(["ID-3", "ID-4"]),
    }
    errs = _run_only_v_cross_0010(v)
    assert errs == []


def test_v_cross_0010_typea_and_typeb_with_overlap():
    """Bei einem überlappenden Identifier muss genau ein Duplikat-Befund entstehen."""
    v = MBDTValidator()
    v.templates = {
        "B99.00": _b99_with_refdate(),
        "B02.00_TypeA": _b02_typea(["ID-1", "ID-2"]),
        "B02.00_TypeB": _b02_typeb(["ID-2", "ID-3"]),  # ID-2 ist Duplikat
    }
    errs = _run_only_v_cross_0010(v)
    assert len(errs) == 1
    issue = errs[0]
    assert issue["template"] == "B02.00_TypeB"
    assert issue["field_code"] == "c0020"
    assert "ID-2" in issue["value"]


def test_v_cross_0010_fallback_to_plain_b02_00():
    """Wenn kein TypeA existiert, aber das generische ``B02.00`` geladen ist,
    muss der Fallback greifen und die Deduplication trotzdem funktionieren."""
    v = MBDTValidator()
    v.templates = {
        "B99.00": _b99_with_refdate(),
        "B02.00": _b02_typea(["ID-9"]),
        "B02.00_TypeB": _b02_typeb(["ID-9"]),
    }
    errs = _run_only_v_cross_0010(v)
    assert len(errs) == 1
    assert "ID-9" in errs[0]["value"]
