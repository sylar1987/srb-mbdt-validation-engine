"""Resubmission-Tracker (AP 4.7)."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ResubmissionRecord:
    resubmission_id: str
    submission_id: str
    origin_run_id: str
    new_run_id: str
    reason: str
    changes: List[str] = field(default_factory=list)
    status: str = "open"  # open | resolved | superseded
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("resubmission requires a reason")
        if self.status not in ("open", "resolved", "superseded"):
            raise ValueError(f"unsupported resubmission status '{self.status}'")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResubmissionTracker:
    """Verknüpft Resubmissions mit Ursprungsläufen und Begründung."""

    def __init__(self) -> None:
        self._records: Dict[str, ResubmissionRecord] = {}

    def record(self, entry: ResubmissionRecord) -> ResubmissionRecord:
        if entry.resubmission_id in self._records:
            raise ValueError(f"resubmission '{entry.resubmission_id}' already exists")
        if entry.origin_run_id == entry.new_run_id:
            raise ValueError("origin and new run must differ for a resubmission")
        self._records[entry.resubmission_id] = entry
        return entry

    def mark_resolved(self, resubmission_id: str) -> ResubmissionRecord:
        record = self._must_get(resubmission_id)
        record.status = "resolved"
        return record

    def supersede(self, resubmission_id: str) -> ResubmissionRecord:
        record = self._must_get(resubmission_id)
        record.status = "superseded"
        return record

    def get(self, resubmission_id: str) -> Optional[ResubmissionRecord]:
        return self._records.get(resubmission_id)

    def for_submission(self, submission_id: str) -> List[ResubmissionRecord]:
        return [r for r in self._records.values() if r.submission_id == submission_id]

    def for_origin_run(self, run_id: str) -> List[ResubmissionRecord]:
        return [r for r in self._records.values() if r.origin_run_id == run_id]

    def all_resubmissions(self) -> List[ResubmissionRecord]:
        return list(self._records.values())

    def _must_get(self, resubmission_id: str) -> ResubmissionRecord:
        record = self._records.get(resubmission_id)
        if record is None:
            raise KeyError(f"unknown resubmission '{resubmission_id}'")
        return record
