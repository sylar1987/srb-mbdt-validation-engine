"""Phase-4-Folge-Härtung: Hashing, RunHistory-Recovery, ResubmissionTracker,
EngineGate, Monitoring, RegressionSuite-Evaluate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.governance import (
    ApprovalStatus,
    ApprovalWorkflow,
    EngineGate,
    GateDecision,
    GateMode,
    ReleaseRecord,
    ReleaseRegistry,
    ReleaseStatus,
)
from app.models import (
    CodelistDefinition,
    DataPointDefinition,
    MetadataPackage,
    TemplateDefinition,
)
from app.operations import (
    OperationsMonitor,
    ResubmissionRecord,
    ResubmissionTracker,
    RunHistory,
    RunRecord,
    RunStatus,
    SubmissionRecord,
    SubmissionRegistry,
    SubmissionStatus,
    validate_resubmission,
)
from app.quality import (
    MetadataAcceptanceChecker,
    RegressionCase,
    RegressionSuite,
)


# --- RunHistory-Recovery ----------------------------------------------------


def test_run_history_finds_orphan_runs() -> None:
    history = RunHistory()
    history.start(RunRecord(run_id="r1"))
    history.start(RunRecord(run_id="r2"))
    history.complete("r2", status=RunStatus.COMPLETED)
    orphans = history.find_orphan_runs()
    assert {r.run_id for r in orphans} == {"r1"}


def test_run_history_mark_orphans_failed_records_recovery_metadata() -> None:
    history = RunHistory()
    history.start(RunRecord(run_id="r1"))
    history.start(RunRecord(run_id="r2"))
    history.complete("r2", status=RunStatus.COMPLETED)

    recovered = history.mark_orphans_failed(
        reason="process crash", actor="ops"
    )
    assert [r.run_id for r in recovered] == ["r1"]
    r1 = history.get("r1")
    assert r1.status == RunStatus.ABANDONED
    assert r1.finished_at
    assert r1.metadata["recovery"]["reason"] == "process crash"
    assert r1.metadata["recovery"]["actor"] == "ops"


def test_run_history_mark_orphans_failed_requires_reason() -> None:
    history = RunHistory()
    history.start(RunRecord(run_id="r1"))
    with pytest.raises(ValueError):
        history.mark_orphans_failed(reason="")


def test_run_history_mark_orphans_failed_rejects_non_terminal_target() -> None:
    history = RunHistory()
    history.start(RunRecord(run_id="r1"))
    with pytest.raises(ValueError):
        history.mark_orphans_failed(reason="x", target_status=RunStatus.STARTED)


def test_run_history_persistence_with_fsync(tmp_path: Path) -> None:
    persist = tmp_path / "runs.jsonl"
    history = RunHistory(persist_path=persist)
    history.start(RunRecord(run_id="r1", submission_id="s1"))
    history.complete("r1", status=RunStatus.COMPLETED, fact_count=4)
    # Datei muss alle Events nach jedem Schritt enthalten (fsync sorgt dafür).
    lines = [ln for ln in persist.read_text("utf-8").splitlines() if ln]
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    assert payloads[0]["event"] == "start"
    assert payloads[1]["event"] == "complete"
    assert payloads[1]["record"]["status"] == RunStatus.COMPLETED

    # Zweite Instanz erkennt offene Runs nach Neuladen sauber.
    history2 = RunHistory(persist_path=persist)
    assert history2.get("r1").status == RunStatus.COMPLETED
    assert history2.find_orphan_runs() == []


def test_run_history_recovery_writes_recovery_event(tmp_path: Path) -> None:
    persist = tmp_path / "runs.jsonl"
    history = RunHistory(persist_path=persist)
    history.start(RunRecord(run_id="r1"))
    history.mark_orphans_failed(reason="abandoned", actor="ops")
    lines = [ln for ln in persist.read_text("utf-8").splitlines() if ln]
    assert any(json.loads(ln)["event"] == "recovery" for ln in lines)


# --- ResubmissionTracker-Validierung ----------------------------------------


def _bootstrap_resubmission_stores() -> tuple[RunHistory, SubmissionRegistry]:
    history = RunHistory()
    submissions = SubmissionRegistry()
    submissions.add(
        SubmissionRecord(
            submission_id="sub-1",
            reporting_date="2026-03-31",
            framework_version="4.2",
        )
    )
    history.start(RunRecord(run_id="run-orig", submission_id="sub-1"))
    history.complete("run-orig", status=RunStatus.COMPLETED)
    history.start(RunRecord(run_id="run-new", submission_id="sub-1"))
    history.complete("run-new", status=RunStatus.COMPLETED)
    return history, submissions


def test_resubmission_tracker_record_checked_happy_path() -> None:
    history, submissions = _bootstrap_resubmission_stores()
    tracker = ResubmissionTracker()
    entry = ResubmissionRecord(
        resubmission_id="rs-1",
        submission_id="sub-1",
        origin_run_id="run-orig",
        new_run_id="run-new",
        reason="LEI fix",
    )
    saved = tracker.record_checked(entry, history, submissions)
    assert saved.resubmission_id == "rs-1"
    assert tracker.get("rs-1") is saved


def test_resubmission_tracker_rejects_unknown_origin_run() -> None:
    history, submissions = _bootstrap_resubmission_stores()
    tracker = ResubmissionTracker()
    with pytest.raises(ValueError):
        tracker.record_checked(
            ResubmissionRecord(
                resubmission_id="rs-1",
                submission_id="sub-1",
                origin_run_id="ghost",
                new_run_id="run-new",
                reason="x",
            ),
            history,
            submissions,
        )


def test_resubmission_tracker_rejects_unknown_submission() -> None:
    history, submissions = _bootstrap_resubmission_stores()
    tracker = ResubmissionTracker()
    with pytest.raises(ValueError):
        tracker.record_checked(
            ResubmissionRecord(
                resubmission_id="rs-1",
                submission_id="sub-ghost",
                origin_run_id="run-orig",
                new_run_id="run-new",
                reason="x",
            ),
            history,
            submissions,
        )


def test_resubmission_tracker_rejects_open_origin_run() -> None:
    history, submissions = _bootstrap_resubmission_stores()
    history.start(RunRecord(run_id="run-open", submission_id="sub-1"))
    tracker = ResubmissionTracker()
    with pytest.raises(ValueError):
        tracker.record_checked(
            ResubmissionRecord(
                resubmission_id="rs-2",
                submission_id="sub-1",
                origin_run_id="run-open",
                new_run_id="run-new",
                reason="x",
            ),
            history,
            submissions,
        )


def test_validate_resubmission_can_require_submission_resubmitted() -> None:
    history, submissions = _bootstrap_resubmission_stores()
    # Submission ist noch DRAFT — nicht resubmitted.
    entry = ResubmissionRecord(
        resubmission_id="rs-1",
        submission_id="sub-1",
        origin_run_id="run-orig",
        new_run_id="run-new",
        reason="x",
    )
    with pytest.raises(ValueError):
        validate_resubmission(
            entry,
            history,
            submissions,
            require_submission_resubmitted=True,
        )


# --- EngineGate -------------------------------------------------------------


def _approved_package_and_release(
    *,
    approve: bool = True,
) -> tuple[MetadataPackage, ReleaseRegistry, ApprovalWorkflow]:
    package = MetadataPackage(
        package_id="PKG-A",
        framework_version="4.2",
        datapoints=[
            DataPointDefinition(
                datapoint_id="dp-1", template_id="B02.00", field_code="c0010"
            )
        ],
        templates=[TemplateDefinition(template_id="B02.00", datapoint_ids=["dp-1"])],
        codelists=[CodelistDefinition(codelist_id="CL-1", values=["A"])],
        rules=[],
    )
    content_hash = package.content_hash()
    releases = ReleaseRegistry()
    releases.register(
        ReleaseRecord(
            release_id="rel-1",
            kind="package",
            version="1.0",
            framework_version="4.2",
            content_hash=content_hash,
            valid_from="2026-01-01",
            valid_to="2026-12-31",
            status=ReleaseStatus.APPROVED,
        )
    )
    workflow = ApprovalWorkflow()
    workflow.register("PKG-A", content_hash)
    if approve:
        workflow.transition("PKG-A", content_hash, ApprovalStatus.VALIDATED, actor="qa")
        workflow.transition("PKG-A", content_hash, ApprovalStatus.REVIEWED, actor="qa")
        workflow.transition(
            "PKG-A",
            content_hash,
            ApprovalStatus.APPROVED,
            actor="qa",
            reason="ok",
        )
    return package, releases, workflow


def test_engine_gate_allows_approved_package() -> None:
    package, releases, workflow = _approved_package_and_release()
    gate = EngineGate(releases, workflow)
    decision = gate.evaluate(package, reporting_date="2026-03-31")
    assert decision.allowed is True
    assert decision.reasons == []
    assert decision.release is not None
    assert decision.acceptance_report is not None


def test_engine_gate_blocks_unapproved_package() -> None:
    package, releases, workflow = _approved_package_and_release(approve=False)
    gate = EngineGate(releases, workflow)
    decision = gate.evaluate(package, reporting_date="2026-03-31")
    assert decision.allowed is False
    assert any("not approved" in r for r in decision.reasons)


def test_engine_gate_blocks_missing_release() -> None:
    package, _, workflow = _approved_package_and_release()
    empty_releases = ReleaseRegistry()
    gate = EngineGate(empty_releases, workflow)
    decision = gate.evaluate(package, reporting_date="2026-03-31")
    assert decision.allowed is False
    assert any("no approved release" in r for r in decision.reasons)


def test_engine_gate_warn_mode_audits_without_blocking() -> None:
    package, releases, workflow = _approved_package_and_release(approve=False)
    gate = EngineGate(releases, workflow, default_mode=GateMode.WARN)
    decision = gate.evaluate(package, reporting_date="2026-03-31")
    assert decision.allowed is True
    # Reasons sind als Warnungen markiert, nicht stillgeschluckt.
    assert any("WARN-ONLY" in w for w in decision.warnings)


def test_engine_gate_blocks_when_acceptance_has_errors() -> None:
    package, releases, workflow = _approved_package_and_release()
    # Erzwinge einen Acceptance-Error: Mindest-Datapoint höher setzen.
    checker = MetadataAcceptanceChecker(min_datapoints=99)
    gate = EngineGate(releases, workflow, acceptance_checker=checker)
    decision = gate.evaluate(package, reporting_date="2026-03-31")
    assert decision.allowed is False
    assert any("acceptance gate" in r for r in decision.reasons)


def test_engine_gate_records_decisions() -> None:
    package, releases, workflow = _approved_package_and_release()
    gate = EngineGate(releases, workflow)
    gate.evaluate(package, reporting_date="2026-03-31")
    gate.evaluate(package, reporting_date="2026-06-30")
    assert len(gate.decisions()) == 2


# --- Monitoring offene Runs --------------------------------------------------


def test_monitoring_reports_open_runs() -> None:
    history = RunHistory()
    history.start(RunRecord(run_id="r1"))
    history.start(RunRecord(run_id="r2"))
    history.complete("r2", status=RunStatus.COMPLETED)
    monitor = OperationsMonitor(history)
    snap = monitor.snapshot()
    assert snap.open_runs == 1
    assert snap.abandoned_runs == 0
    assert "r1" in monitor.orphan_run_ids()


def test_monitoring_counts_abandoned_after_recovery() -> None:
    history = RunHistory()
    history.start(RunRecord(run_id="r1"))
    history.mark_orphans_failed(reason="crash", actor="ops")
    monitor = OperationsMonitor(history)
    snap = monitor.snapshot()
    assert snap.abandoned_runs == 1
    assert snap.open_runs == 0


# --- RegressionSuite-Evaluate -----------------------------------------------


def test_regression_suite_evaluate_passes_on_match() -> None:
    suite = RegressionSuite("phase4")
    suite.add_case(
        RegressionCase(
            case_id="c1",
            description="x",
            expected_status="pass",
            expected_error_count=0,
        )
    )
    result = suite.evaluate("c1", actual_error_count=0)
    assert result.status == "passed"
    assert result.actual_error_count == 0
    assert result.notes == ""


def test_regression_suite_evaluate_fails_on_error_count_mismatch() -> None:
    suite = RegressionSuite("phase4")
    suite.add_case(
        RegressionCase(
            case_id="c1",
            description="x",
            expected_status="pass",
            expected_error_count=0,
        )
    )
    result = suite.evaluate("c1", actual_error_count=2)
    assert result.status == "failed"
    assert "error_count" in result.notes


def test_regression_suite_evaluate_fails_on_status_mismatch() -> None:
    suite = RegressionSuite("phase4")
    suite.add_case(
        RegressionCase(
            case_id="c1",
            description="x",
            expected_status="fail",
            expected_error_count=3,
        )
    )
    # Erwartet fail+3, actual pass+0 ergibt zwei Diskrepanzen.
    result = suite.evaluate("c1", actual_error_count=0)
    assert result.status == "failed"
    assert "status" in result.notes
    assert "error_count" in result.notes
