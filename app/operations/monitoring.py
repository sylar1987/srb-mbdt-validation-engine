"""Einfache Metriken über Runs (AP 4.8)."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

from app.operations.run_history import RunHistory, RunStatus


@dataclass
class MonitoringSnapshot:
    total_runs: int = 0
    runs_by_status: Dict[str, int] = field(default_factory=dict)
    error_count_total: int = 0
    warning_count_total: int = 0
    error_classes: Dict[str, int] = field(default_factory=dict)
    artifacts_count: int = 0
    runs_with_zero_errors: int = 0
    success_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OperationsMonitor:
    """Berechnet einen Snapshot aus dem ``RunHistory``-Bestand."""

    def __init__(self, history: RunHistory) -> None:
        self._history = history

    def snapshot(self) -> MonitoringSnapshot:
        runs = self._history.all_runs()
        snapshot = MonitoringSnapshot(total_runs=len(runs))
        if not runs:
            return snapshot

        for run in runs:
            snapshot.runs_by_status[run.status] = snapshot.runs_by_status.get(run.status, 0) + 1
            snapshot.error_count_total += run.error_count
            snapshot.warning_count_total += run.warning_count
            snapshot.artifacts_count += len(run.artifacts)
            for klass, count in run.error_classes.items():
                snapshot.error_classes[klass] = snapshot.error_classes.get(klass, 0) + count
            if run.error_count == 0 and run.status == RunStatus.COMPLETED:
                snapshot.runs_with_zero_errors += 1

        completed = snapshot.runs_by_status.get(RunStatus.COMPLETED, 0)
        snapshot.success_rate = completed / len(runs) if runs else 0.0
        return snapshot

    def top_error_classes(self, limit: int = 5) -> List[Dict[str, Any]]:
        snapshot = self.snapshot()
        sorted_items = sorted(snapshot.error_classes.items(), key=lambda kv: kv[1], reverse=True)
        return [{"error_class": name, "count": count} for name, count in sorted_items[:limit]]
