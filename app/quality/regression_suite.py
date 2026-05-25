"""Regression-Suite-Modelle (AP 4.6).

MVP: nur Modell und Run-Tracking, keine echte End-to-End-Ausführung
großer Submissions. Echte Submission-Sets folgen in einer späteren
Phase-4-Iteration.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class RegressionCase:
    case_id: str
    description: str
    framework_version: str = ""
    fixture_path: str = ""
    expected_status: str = "pass"  # pass | fail
    expected_error_count: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RegressionRunResult:
    case_id: str
    status: str  # passed | failed | skipped
    actual_error_count: int = 0
    notes: str = ""
    executed_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RegressionSuite:
    """Hält Cases und ihre letzten Ergebnisse."""

    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("regression suite needs a name")
        self.name = name
        self._cases: Dict[str, RegressionCase] = {}
        self._latest: Dict[str, RegressionRunResult] = {}

    def add_case(self, case: RegressionCase) -> RegressionCase:
        if case.case_id in self._cases:
            raise ValueError(f"case '{case.case_id}' already exists in suite '{self.name}'")
        self._cases[case.case_id] = case
        return case

    def record_result(self, result: RegressionRunResult) -> RegressionRunResult:
        if result.case_id not in self._cases:
            raise KeyError(f"unknown regression case '{result.case_id}'")
        if result.status not in ("passed", "failed", "skipped"):
            raise ValueError(f"unsupported regression result status '{result.status}'")
        self._latest[result.case_id] = result
        return result

    def case(self, case_id: str) -> Optional[RegressionCase]:
        return self._cases.get(case_id)

    def latest_result(self, case_id: str) -> Optional[RegressionRunResult]:
        return self._latest.get(case_id)

    def cases(self) -> List[RegressionCase]:
        return list(self._cases.values())

    def summary(self) -> Dict[str, Any]:
        results = self._latest
        total = len(self._cases)
        executed = len(results)
        passed = sum(1 for r in results.values() if r.status == "passed")
        failed = sum(1 for r in results.values() if r.status == "failed")
        skipped = sum(1 for r in results.values() if r.status == "skipped")
        return {
            "suite": self.name,
            "case_count": total,
            "executed": executed,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "missing_executions": [
                case_id for case_id in self._cases if case_id not in results
            ],
        }
