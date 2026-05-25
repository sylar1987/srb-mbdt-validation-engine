"""Auditabfragen über Runs, Submissions und Resubmissions (AP 4.7)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.operations.run_history import RunHistory
from app.operations.submission_registry import SubmissionRegistry
from app.operations.resubmission_tracker import ResubmissionTracker


class AuditQuery:
    """Schreibgeschützter Adapter über die Operations-Stores."""

    def __init__(
        self,
        history: RunHistory,
        submissions: SubmissionRegistry,
        resubmissions: ResubmissionTracker,
    ) -> None:
        self._history = history
        self._submissions = submissions
        self._resubmissions = resubmissions

    def run_detail(self, run_id: str) -> Dict[str, Any]:
        run = self._history.get(run_id)
        if run is None:
            raise KeyError(f"unknown run '{run_id}'")
        submission = self._submissions.get(run.submission_id) if run.submission_id else None
        resubmissions = self._resubmissions.for_origin_run(run_id)
        return {
            "run": run.to_dict(),
            "submission": submission.to_dict() if submission else None,
            "resubmissions": [r.to_dict() for r in resubmissions],
        }

    def submission_history(self, submission_id: str) -> Dict[str, Any]:
        submission = self._submissions.get(submission_id)
        if submission is None:
            raise KeyError(f"unknown submission '{submission_id}'")
        runs = self._history.runs_for_submission(submission_id)
        resubmissions = self._resubmissions.for_submission(submission_id)
        return {
            "submission": submission.to_dict(),
            "runs": [r.to_dict() for r in runs],
            "resubmissions": [r.to_dict() for r in resubmissions],
        }

    def search_runs(
        self,
        reporting_date: Optional[str] = None,
        framework_version: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for run in self._history.all_runs():
            if reporting_date is not None and run.reporting_date != reporting_date:
                continue
            if framework_version is not None and run.framework_version != framework_version:
                continue
            if status is not None and run.status != status:
                continue
            results.append(run.to_dict())
        return results
