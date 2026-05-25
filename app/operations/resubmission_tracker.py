"""Resubmission-Tracker (AP 4.7)."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.operations.run_history import RunHistory
    from app.operations.submission_registry import SubmissionRegistry


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

    def record_checked(
        self,
        entry: ResubmissionRecord,
        run_history: "RunHistory",
        submission_registry: "SubmissionRegistry",
        require_submission_resubmitted: bool = False,
    ) -> ResubmissionRecord:
        """Schreibe eine Resubmission, prüfe vorher referenzielle Integrität.

        Variante zu ``record`` für den sicheren Pfad. Bricht ab, wenn

        * ``submission_id`` nicht in ``submission_registry`` existiert,
        * ``origin_run_id`` oder ``new_run_id`` nicht in ``run_history``
          existieren,
        * ``submission_id`` der referenzierten Runs nicht zur Resubmission-
          Submission passt,
        * der Origin-Run noch nicht abgeschlossen ist (``finished_at``
          leer), oder
        * ``require_submission_resubmitted=True`` gesetzt ist und die
          Submission noch nicht im Status ``resubmitted`` steht.

        Die Bestandsmethode ``record`` bleibt unverändert verfügbar, damit
        Aufrufer mit losen Strings nicht hart brechen.
        """
        validate_resubmission(
            entry,
            run_history=run_history,
            submission_registry=submission_registry,
            require_submission_resubmitted=require_submission_resubmitted,
        )
        return self.record(entry)

    def _must_get(self, resubmission_id: str) -> ResubmissionRecord:
        record = self._records.get(resubmission_id)
        if record is None:
            raise KeyError(f"unknown resubmission '{resubmission_id}'")
        return record


def validate_resubmission(
    entry: ResubmissionRecord,
    run_history: "RunHistory",
    submission_registry: "SubmissionRegistry",
    require_submission_resubmitted: bool = False,
) -> None:
    """Reine Validierung gegen die Bestandsstores — wirft bei Verstoß.

    Als Service-Funktion verfügbar, damit Aufrufer die Prüfung auch ohne
    direkten Tracker-Bezug nutzen können (z. B. in einer Engine-Stufe).
    """
    if entry.submission_id and submission_registry.get(entry.submission_id) is None:
        raise ValueError(
            f"unknown submission '{entry.submission_id}' for resubmission "
            f"'{entry.resubmission_id}'"
        )
    origin = run_history.get(entry.origin_run_id)
    if origin is None:
        raise ValueError(
            f"unknown origin run '{entry.origin_run_id}' for resubmission "
            f"'{entry.resubmission_id}'"
        )
    new_run = run_history.get(entry.new_run_id)
    if new_run is None:
        raise ValueError(
            f"unknown new run '{entry.new_run_id}' for resubmission "
            f"'{entry.resubmission_id}'"
        )
    if entry.submission_id and origin.submission_id and origin.submission_id != entry.submission_id:
        raise ValueError(
            f"origin run '{entry.origin_run_id}' belongs to submission "
            f"'{origin.submission_id}', not '{entry.submission_id}'"
        )
    if entry.submission_id and new_run.submission_id and new_run.submission_id != entry.submission_id:
        raise ValueError(
            f"new run '{entry.new_run_id}' belongs to submission "
            f"'{new_run.submission_id}', not '{entry.submission_id}'"
        )
    if not origin.finished_at:
        raise ValueError(
            f"origin run '{entry.origin_run_id}' is still open; cannot link resubmission"
        )
    if require_submission_resubmitted and entry.submission_id:
        sub = submission_registry.get(entry.submission_id)
        if sub is not None and sub.status != "resubmitted":
            raise ValueError(
                f"submission '{entry.submission_id}' must be in status 'resubmitted', "
                f"is '{sub.status}'"
            )
