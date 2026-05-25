"""Phase-4-Tests: Operations-Layer."""

from __future__ import annotations

import pytest

from app.operations import (
    AuditQuery,
    OperationsMonitor,
    ResubmissionRecord,
    ResubmissionTracker,
    RunHistory,
    RunRecord,
    RunStatus,
    SubmissionRecord,
    SubmissionRegistry,
    SubmissionStatus,
)


# --- RunHistory ------------------------------------------------------------


def test_run_history_start_complete_lifecycle() -> None:
    history = RunHistory()
    record = history.start(
        RunRecord(
            run_id="run-1",
            submission_id="sub-1",
            reporting_date="2026-03-31",
            framework_version="4.2",
            metadata_version="hash-1",
        )
    )
    assert record.status == RunStatus.STARTED
    history.complete(
        "run-1",
        status=RunStatus.COMPLETED,
        error_count=0,
        warning_count=2,
        fact_count=10,
        rule_count=5,
        artifacts=["facts.csv", "metadata.json"],
        error_classes={},
    )
    stored = history.get("run-1")
    assert stored is not None
    assert stored.status == RunStatus.COMPLETED
    assert stored.finished_at
    assert stored.fact_count == 10


def test_run_history_complete_twice_raises() -> None:
    history = RunHistory()
    history.start(RunRecord(run_id="run-x"))
    history.complete("run-x")
    with pytest.raises(ValueError):
        history.complete("run-x")


def test_run_history_duplicate_start_raises() -> None:
    history = RunHistory()
    history.start(RunRecord(run_id="run-x"))
    with pytest.raises(ValueError):
        history.start(RunRecord(run_id="run-x"))


def test_run_history_persistence_round_trip(tmp_path) -> None:
    persist = tmp_path / "runs.jsonl"
    history = RunHistory(persist_path=persist)
    history.start(
        RunRecord(
            run_id="run-1",
            submission_id="sub-1",
            framework_version="4.2",
        )
    )
    history.complete("run-1", status=RunStatus.COMPLETED, fact_count=3)

    second = RunHistory(persist_path=persist)
    record = second.get("run-1")
    assert record is not None
    assert record.status == RunStatus.COMPLETED
    assert record.fact_count == 3


# --- SubmissionRegistry ----------------------------------------------------


def test_submission_registry_status_updates_and_artifacts() -> None:
    registry = SubmissionRegistry()
    registry.add(
        SubmissionRecord(
            submission_id="sub-1",
            reporting_date="2026-03-31",
            framework_version="4.2",
            entity="ENTITY-A",
        )
    )
    registry.update_status("sub-1", SubmissionStatus.READY)
    registry.attach_artifact("sub-1", "package.zip")
    registry.update_status("sub-1", SubmissionStatus.SUBMITTED)
    registry.update_status("sub-1", SubmissionStatus.ACCEPTED)

    record = registry.get("sub-1")
    assert record is not None
    assert record.status == SubmissionStatus.ACCEPTED
    assert record.artifacts == ["package.zip"]


def test_submission_registry_blocks_post_terminal_status() -> None:
    registry = SubmissionRegistry()
    registry.add(
        SubmissionRecord(
            submission_id="sub-1",
            reporting_date="2026-03-31",
            framework_version="4.2",
            status=SubmissionStatus.ACCEPTED,
        )
    )
    with pytest.raises(ValueError):
        registry.update_status("sub-1", SubmissionStatus.SUBMITTED)
    # Resubmission ist explizit erlaubt:
    registry.update_status("sub-1", SubmissionStatus.RESUBMITTED)


# --- ResubmissionTracker ---------------------------------------------------


def test_resubmission_tracker_links_runs() -> None:
    tracker = ResubmissionTracker()
    tracker.record(
        ResubmissionRecord(
            resubmission_id="rs-1",
            submission_id="sub-1",
            origin_run_id="run-1",
            new_run_id="run-2",
            reason="LEI corrected after EBA rejection",
            changes=["c0010=LEI fixed"],
        )
    )
    assert tracker.for_submission("sub-1")
    assert tracker.for_origin_run("run-1")
    tracker.mark_resolved("rs-1")
    assert tracker.get("rs-1").status == "resolved"


def test_resubmission_tracker_validation() -> None:
    with pytest.raises(ValueError):
        ResubmissionRecord(
            resubmission_id="rs-bad",
            submission_id="sub",
            origin_run_id="run-1",
            new_run_id="run-2",
            reason="",
        )
    tracker = ResubmissionTracker()
    with pytest.raises(ValueError):
        tracker.record(
            ResubmissionRecord(
                resubmission_id="rs-same",
                submission_id="sub",
                origin_run_id="run-x",
                new_run_id="run-x",
                reason="loop",
            )
        )


# --- Monitoring ------------------------------------------------------------


def test_operations_monitor_snapshot_aggregates_counts() -> None:
    history = RunHistory()
    history.start(RunRecord(run_id="r1"))
    history.complete(
        "r1",
        status=RunStatus.COMPLETED,
        error_count=0,
        warning_count=1,
        error_classes={"CONF030": 1},
    )
    history.start(RunRecord(run_id="r2"))
    history.complete(
        "r2",
        status=RunStatus.FAILED,
        error_count=3,
        error_classes={"L1": 2, "L3": 1},
    )

    monitor = OperationsMonitor(history)
    snap = monitor.snapshot()
    assert snap.total_runs == 2
    assert snap.runs_by_status.get(RunStatus.COMPLETED) == 1
    assert snap.runs_by_status.get(RunStatus.FAILED) == 1
    assert snap.error_count_total == 3
    assert snap.warning_count_total == 1
    assert snap.error_classes["L1"] == 2

    top = monitor.top_error_classes(limit=2)
    assert top[0]["error_class"] == "L1"


# --- AuditQuery ------------------------------------------------------------


def test_audit_query_run_and_submission_views() -> None:
    history = RunHistory()
    submissions = SubmissionRegistry()
    resubmissions = ResubmissionTracker()

    submissions.add(
        SubmissionRecord(
            submission_id="sub-1",
            reporting_date="2026-03-31",
            framework_version="4.2",
        )
    )
    history.start(
        RunRecord(
            run_id="run-1",
            submission_id="sub-1",
            reporting_date="2026-03-31",
            framework_version="4.2",
        )
    )
    history.complete("run-1", status=RunStatus.COMPLETED)
    history.start(
        RunRecord(
            run_id="run-2",
            submission_id="sub-1",
            reporting_date="2026-03-31",
            framework_version="4.2",
        )
    )
    history.complete("run-2", status=RunStatus.COMPLETED)
    resubmissions.record(
        ResubmissionRecord(
            resubmission_id="rs-1",
            submission_id="sub-1",
            origin_run_id="run-1",
            new_run_id="run-2",
            reason="data correction",
        )
    )

    audit = AuditQuery(history, submissions, resubmissions)
    detail = audit.run_detail("run-1")
    assert detail["run"]["run_id"] == "run-1"
    assert detail["submission"]["submission_id"] == "sub-1"
    assert len(detail["resubmissions"]) == 1

    sub = audit.submission_history("sub-1")
    assert len(sub["runs"]) == 2
    assert len(sub["resubmissions"]) == 1

    search = audit.search_runs(framework_version="4.2", status=RunStatus.COMPLETED)
    assert {r["run_id"] for r in search} == {"run-1", "run-2"}
