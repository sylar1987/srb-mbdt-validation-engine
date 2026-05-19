"""End-to-End-Test: Runner gegen ein synthetisches CSV-Bundle."""

from __future__ import annotations

from pathlib import Path

from app.runner import Runner
from app.settings import EngineSettings


def _write_csv(path: Path, header: list, rows: list):
    with open(path, "w", encoding="utf-8-sig") as fh:
        fh.write(";".join(header) + "\n")
        for r in rows:
            fh.write(";".join(r) + "\n")


def test_runner_missing_b99(tmp_path: Path):
    """Ohne B99.00 muss SYS_002 ausgelöst werden.

    Nach BUG-17-Fix (v_CROSS_0010) ist es sicher, ``B02.00_TypeA`` allein
    zu laden, ohne dass die CROSS-Regel mit ``ValueError`` crasht.
    """
    f = tmp_path / "B02.00_TypeA.csv"
    _write_csv(f, ["0010", "0020"], [["1", "X"]])
    runner = Runner(EngineSettings())
    runner.load_csv_dir(tmp_path)
    summary = runner.validate()
    rule_ids = {i.rule_id for i in runner.context.issues}
    assert "SYS_002" in rule_ids
    assert summary.errors >= 1


def test_runner_no_templates(tmp_path: Path):
    """Bei leerem Verzeichnis muss SYS_001 ausgelöst werden."""
    runner = Runner(EngineSettings())
    runner.load_csv_dir(tmp_path)
    summary = runner.validate()
    rule_ids = {i.rule_id for i in runner.context.issues}
    assert "SYS_001" in rule_ids
    assert summary.errors == 1


def test_runner_with_b99(tmp_path: Path):
    """Mit B99.00 + Reference Date läuft die Validation ohne SYS_002 durch."""
    b99 = tmp_path / "B99.00.csv"
    # B99 minimal: reporting reference date in c0070
    _write_csv(b99, ["0010", "0070"], [["x", "2024-12-31"]])
    runner = Runner(EngineSettings())
    runner.load_csv_dir(tmp_path)
    summary = runner.validate()
    rule_ids = {i.rule_id for i in runner.context.issues}
    assert "SYS_002" not in rule_ids
    assert runner.context.reference_date == "2024-12-31"
    # Summary muss konsistent sein
    assert summary.total == len(runner.context.issues)
