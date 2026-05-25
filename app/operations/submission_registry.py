"""Submission-Registry (AP 4.7).

Eine Submission ist ein fachliches Reporting-Ereignis (z. B. SRB-Q2-2026).
Mehrere Runs / Resubmissions können auf dieselbe Submission verweisen.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class SubmissionStatus:
    DRAFT = "draft"
    READY = "ready"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RESUBMITTED = "resubmitted"

    ALL = (DRAFT, READY, SUBMITTED, ACCEPTED, REJECTED, RESUBMITTED)


@dataclass
class SubmissionRecord:
    submission_id: str
    reporting_date: str
    framework_version: str
    entity: str = ""
    status: str = SubmissionStatus.DRAFT
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )

    def __post_init__(self) -> None:
        if self.status not in SubmissionStatus.ALL:
            raise ValueError(f"unsupported submission status '{self.status}'")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_TERMINAL = (SubmissionStatus.ACCEPTED,)


class SubmissionRegistry:
    """In-Memory-Registry mit kontrollierten Statusübergängen."""

    def __init__(self) -> None:
        self._records: Dict[str, SubmissionRecord] = {}

    def add(self, record: SubmissionRecord) -> SubmissionRecord:
        if record.submission_id in self._records:
            raise ValueError(f"submission '{record.submission_id}' already exists")
        self._records[record.submission_id] = record
        return record

    def update_status(self, submission_id: str, new_status: str) -> SubmissionRecord:
        if new_status not in SubmissionStatus.ALL:
            raise ValueError(f"unsupported submission status '{new_status}'")
        record = self._must_get(submission_id)
        if record.status in _TERMINAL and new_status != SubmissionStatus.RESUBMITTED:
            raise ValueError(
                f"submission '{submission_id}' is in terminal status '{record.status}'"
            )
        record.status = new_status
        record.updated_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
        return record

    def attach_artifact(self, submission_id: str, artifact: str) -> SubmissionRecord:
        record = self._must_get(submission_id)
        if artifact not in record.artifacts:
            record.artifacts.append(artifact)
        record.updated_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
        return record

    def get(self, submission_id: str) -> Optional[SubmissionRecord]:
        return self._records.get(submission_id)

    def all_submissions(self) -> List[SubmissionRecord]:
        return list(self._records.values())

    def for_reporting_date(self, reporting_date: str) -> List[SubmissionRecord]:
        return [r for r in self._records.values() if r.reporting_date == reporting_date]

    def _must_get(self, submission_id: str) -> SubmissionRecord:
        record = self._records.get(submission_id)
        if record is None:
            raise KeyError(f"unknown submission '{submission_id}'")
        return record
