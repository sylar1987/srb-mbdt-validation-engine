"""Golden-Master-Regressionstest gegen die Mini-Fixture.

Vergleicht den Issue-Schlüsselsatz (``rule_id, template, row, field_code,
severity``) gegen ``expected_issue_keys.json``. Läuft sowohl im nativen
als auch im Legacy-Modus – die Parität ist Teil der Phase-1.5-Akzeptanz.

Einschränkung: Es liegen keine realen SRB-Submissions im Repository.
Diese Suite ist eine synthetische Mindestabdeckung, kein Vollersatz für
echte Bestandsdaten.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.runner import Runner
from app.settings import EngineSettings

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "golden_master_min"
EXPECTED_PATH = FIXTURE_DIR / "expected_issue_keys.json"


def _run(use_native: bool):
    s = EngineSettings()
    s.extra["use_native_validators"] = use_native
    r = Runner(s)
    r.load_csv_dir(FIXTURE_DIR)
    r.validate()
    return r


def _issue_keys(runner: Runner):
    return sorted(
        [i.rule_id, i.template, i.row, i.field_code, i.severity]
        for i in runner.context.issues
    )


@pytest.fixture(scope="module")
def expected_keys():
    return [tuple(x) for x in json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))]


@pytest.mark.parametrize("use_native", [True, False])
def test_golden_master_min(use_native, expected_keys):
    runner = _run(use_native)
    actual = [tuple(x) for x in _issue_keys(runner)]
    assert actual == expected_keys


def test_golden_master_manifest_has_run_id():
    """Manifest skeleton ist Pflicht: jeder Lauf hat eine run_id."""
    runner = _run(True)
    assert runner.manifest is not None
    assert runner.manifest.run_id
    assert runner.manifest.issue_count == len(runner.context.issues)


def test_golden_master_bug17_cross_rule_safe():
    """Smoke-Check, dass v_CROSS_0010 in dieser Fixture nicht crasht
    (Regressionsschutz für BUG-17 auf Runner-Ebene)."""
    runner = _run(True)
    # Die Fixture enthält kein B02.00_TypeA, also wirft die Regel nichts –
    # entscheidend ist, dass der Runner ohne Exception durchläuft.
    assert any(i.rule_id.startswith("v_") for i in runner.context.issues)
