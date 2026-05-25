"""Persistente Run-Historie (AP 4.7).

In der MVP-Variante speichern wir Run-Records in memory plus optional
JSON-Lines auf der Platte. Die Persistenz ist append-only — historische
Runs lassen sich nicht überschreiben, was Phase-4-Audit-Anforderungen
direkt entgegenkommt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class RunStatus:
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # z. B. wegen NotApprovedError

    ALL = (STARTED, COMPLETED, FAILED, BLOCKED)


@dataclass
class RunRecord:
    run_id: str
    submission_id: str = ""
    reporting_date: str = ""
    framework_version: str = ""
    metadata_version: str = ""
    rule_version: str = ""
    input_hash: str = ""
    status: str = RunStatus.STARTED
    error_count: int = 0
    warning_count: int = 0
    fact_count: int = 0
    rule_count: int = 0
    artifacts: List[str] = field(default_factory=list)
    started_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )
    finished_at: str = ""
    error_classes: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in RunStatus.ALL:
            raise ValueError(f"unsupported run status '{self.status}'")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RunHistory:
    """Append-only Run-Speicher mit optionaler Persistenz."""

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._records: Dict[str, RunRecord] = {}
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path is not None:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load()

    # -- mutation ---------------------------------------------------------
    def start(self, record: RunRecord) -> RunRecord:
        if record.run_id in self._records:
            raise ValueError(f"run '{record.run_id}' already exists")
        self._records[record.run_id] = record
        self._append_to_disk(record, event="start")
        return record

    def complete(
        self,
        run_id: str,
        status: str = RunStatus.COMPLETED,
        error_count: int = 0,
        warning_count: int = 0,
        fact_count: int = 0,
        rule_count: int = 0,
        artifacts: Optional[Iterable[str]] = None,
        error_classes: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RunRecord:
        if status not in RunStatus.ALL:
            raise ValueError(f"unsupported run status '{status}'")
        record = self._must_get(run_id)
        if record.finished_at:
            raise ValueError(f"run '{run_id}' already finished")
        record.status = status
        record.error_count = error_count
        record.warning_count = warning_count
        record.fact_count = fact_count
        record.rule_count = rule_count
        if artifacts is not None:
            record.artifacts = list(artifacts)
        if error_classes is not None:
            record.error_classes = dict(error_classes)
        if metadata is not None:
            record.metadata.update(metadata)
        record.finished_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
        self._append_to_disk(record, event="complete")
        return record

    # -- queries ----------------------------------------------------------
    def get(self, run_id: str) -> Optional[RunRecord]:
        return self._records.get(run_id)

    def all_runs(self) -> List[RunRecord]:
        return list(self._records.values())

    def runs_for_submission(self, submission_id: str) -> List[RunRecord]:
        return [r for r in self._records.values() if r.submission_id == submission_id]

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        with self._persist_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                record = RunRecord(**payload["record"])
                self._records[record.run_id] = record

    def _append_to_disk(self, record: RunRecord, event: str) -> None:
        if self._persist_path is None:
            return
        payload = {"event": event, "record": record.to_dict()}
        with self._persist_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _must_get(self, run_id: str) -> RunRecord:
        record = self._records.get(run_id)
        if record is None:
            raise KeyError(f"unknown run '{run_id}'")
        return record
