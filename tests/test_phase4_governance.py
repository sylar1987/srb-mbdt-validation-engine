"""Phase-4-Tests: Governance-Layer."""

from __future__ import annotations

import pytest

from app.governance import (
    ApprovalStatus,
    ApprovalWorkflow,
    ChangeControlReport,
    NotApprovedError,
    OverrideEntry,
    OverrideRegistry,
    OverrideType,
    ReleaseRecord,
    ReleaseRegistry,
    ReleaseStatus,
    RuleReview,
    RuleReviewRegistry,
    RuleReviewStatus,
    RuleTestStatus,
    build_change_control_report,
    diff_rules,
    rule_summary,
)
from app.metadata.metadata_versioning import PackageDelta
from app.models import MetadataPackage, RuleDefinitionV2
from app.quality.metadata_acceptance import (
    AcceptanceFinding,
    AcceptanceReport,
    MetadataAcceptanceChecker,
)


# --- ReleaseRegistry --------------------------------------------------------


def test_release_registry_resolves_by_reporting_date() -> None:
    registry = ReleaseRegistry()
    registry.register(
        ReleaseRecord(
            release_id="fw-4.1",
            kind="framework",
            version="4.1",
            framework_version="4.1",
            valid_from="2025-01-01",
            valid_to="2026-03-30",
            status=ReleaseStatus.APPROVED,
        )
    )
    registry.register(
        ReleaseRecord(
            release_id="fw-4.2",
            kind="framework",
            version="4.2",
            framework_version="4.2",
            valid_from="2026-03-31",
            valid_to="2027-12-31",
            status=ReleaseStatus.APPROVED,
        )
    )

    resolved_q1 = registry.resolve("framework", "2026-03-15")
    resolved_q2 = registry.resolve("framework", "2026-06-30")
    assert resolved_q1.release_id == "fw-4.1"
    assert resolved_q2.release_id == "fw-4.2"


def test_release_registry_blocks_overlapping_active_records() -> None:
    registry = ReleaseRegistry()
    registry.register(
        ReleaseRecord(
            release_id="fw-A",
            kind="framework",
            version="1.0",
            framework_version="4.2",
            valid_from="2026-01-01",
            valid_to="2026-12-31",
            status=ReleaseStatus.APPROVED,
        )
    )
    with pytest.raises(ValueError):
        registry.register(
            ReleaseRecord(
                release_id="fw-B",
                kind="framework",
                version="1.1",
                framework_version="4.2",
                valid_from="2026-06-01",
                valid_to="2027-06-30",
                status=ReleaseStatus.APPROVED,
            )
        )


def test_release_registry_prefers_specific_over_generic() -> None:
    """Framework-spezifische Releases müssen vor Generic-Releases gewählt werden."""
    registry = ReleaseRegistry()
    registry.register(
        ReleaseRecord(
            release_id="generic",
            kind="package",
            version="1.0",
            framework_version="",
            valid_from="2026-01-01",
            valid_to="2026-12-31",
            status=ReleaseStatus.APPROVED,
        )
    )
    registry.register(
        ReleaseRecord(
            release_id="specific-4.2",
            kind="package",
            version="1.1",
            framework_version="4.2",
            valid_from="2026-01-01",
            valid_to="2026-12-31",
            status=ReleaseStatus.APPROVED,
        )
    )
    chosen = registry.resolve("package", "2026-06-30", framework_version="4.2")
    assert chosen.release_id == "specific-4.2"


def test_release_registry_generic_is_fallback_when_no_specific() -> None:
    """Ohne spezifischen Treffer fällt resolve auf einen Generic-Release zurück."""
    registry = ReleaseRegistry()
    registry.register(
        ReleaseRecord(
            release_id="generic",
            kind="package",
            version="1.0",
            framework_version="",
            valid_from="2026-01-01",
            valid_to="2026-12-31",
            status=ReleaseStatus.APPROVED,
        )
    )
    chosen = registry.resolve("package", "2026-06-30", framework_version="4.2")
    assert chosen.release_id == "generic"


def test_release_registry_generic_and_specific_may_coexist() -> None:
    """Generic und framework-spezifisch dürfen parallel registriert sein."""
    registry = ReleaseRegistry()
    registry.register(
        ReleaseRecord(
            release_id="generic",
            kind="package",
            version="1.0",
            framework_version="",
            valid_from="2026-01-01",
            valid_to="2026-12-31",
            status=ReleaseStatus.APPROVED,
        )
    )
    # Spezifischer Release im selben Fenster darf trotzdem registriert werden.
    registry.register(
        ReleaseRecord(
            release_id="specific-4.2",
            kind="package",
            version="1.1",
            framework_version="4.2",
            valid_from="2026-01-01",
            valid_to="2026-12-31",
            status=ReleaseStatus.APPROVED,
        )
    )
    assert {r.release_id for r in registry.list("package")} == {
        "generic",
        "specific-4.2",
    }


def test_release_registry_skips_deprecated_releases() -> None:
    registry = ReleaseRegistry()
    registry.register(
        ReleaseRecord(
            release_id="old",
            kind="package",
            version="1.0",
            framework_version="4.2",
            valid_from="2026-01-01",
            valid_to="2026-06-30",
            status=ReleaseStatus.APPROVED,
        )
    )
    registry.deprecate("old")

    with pytest.raises(LookupError):
        registry.resolve("package", "2026-03-15", framework_version="4.2")


def test_release_registry_resolve_unknown_raises() -> None:
    registry = ReleaseRegistry()
    with pytest.raises(LookupError):
        registry.resolve("framework", "2026-01-01")


def test_release_registry_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        ReleaseRecord(release_id="x", kind="unknown", version="1")


# --- ApprovalWorkflow ------------------------------------------------------


def test_approval_workflow_full_happy_path() -> None:
    workflow = ApprovalWorkflow()
    workflow.register("PKG-1", "hash-1")
    assert workflow.status("PKG-1", "hash-1") == ApprovalStatus.IMPORTED

    workflow.transition("PKG-1", "hash-1", ApprovalStatus.VALIDATED, actor="alice")
    workflow.transition("PKG-1", "hash-1", ApprovalStatus.REVIEWED, actor="bob")
    workflow.transition(
        "PKG-1", "hash-1", ApprovalStatus.APPROVED, actor="boss", reason="legal sign-off"
    )

    assert workflow.is_approved("PKG-1", "hash-1")
    workflow.ensure_approved("PKG-1", "hash-1")

    events = workflow.events_for("PKG-1")
    assert [e.to_status for e in events] == [
        ApprovalStatus.IMPORTED,
        ApprovalStatus.VALIDATED,
        ApprovalStatus.REVIEWED,
        ApprovalStatus.APPROVED,
    ]


def test_approval_workflow_blocks_illegal_transition() -> None:
    workflow = ApprovalWorkflow()
    workflow.register("PKG-2", "hash-2")
    with pytest.raises(ValueError):
        workflow.transition(
            "PKG-2", "hash-2", ApprovalStatus.APPROVED, actor="x", reason="too early"
        )


def test_approval_workflow_approve_requires_reason() -> None:
    workflow = ApprovalWorkflow()
    workflow.register("PKG-3", "hash-3")
    workflow.transition("PKG-3", "hash-3", ApprovalStatus.VALIDATED, actor="a")
    workflow.transition("PKG-3", "hash-3", ApprovalStatus.REVIEWED, actor="b")
    with pytest.raises(ValueError):
        workflow.transition("PKG-3", "hash-3", ApprovalStatus.APPROVED, actor="boss")


def test_approval_workflow_ensure_approved_raises_for_other_hash() -> None:
    workflow = ApprovalWorkflow()
    workflow.register("PKG-4", "hash-4")
    workflow.transition("PKG-4", "hash-4", ApprovalStatus.VALIDATED, actor="a")
    workflow.transition("PKG-4", "hash-4", ApprovalStatus.REVIEWED, actor="b")
    workflow.transition(
        "PKG-4", "hash-4", ApprovalStatus.APPROVED, actor="boss", reason="ok"
    )

    workflow.register("PKG-4", "hash-4b")
    with pytest.raises(NotApprovedError):
        workflow.ensure_approved("PKG-4", "hash-4b")


def test_approval_workflow_deprecation_requires_reason() -> None:
    """DEPRECATED ist nachvollziehbar zu begründen."""
    workflow = ApprovalWorkflow()
    workflow.register("PKG-DEP", "hash-dep")
    workflow.transition("PKG-DEP", "hash-dep", ApprovalStatus.VALIDATED, actor="a")
    workflow.transition("PKG-DEP", "hash-dep", ApprovalStatus.REVIEWED, actor="b")
    workflow.transition(
        "PKG-DEP", "hash-dep", ApprovalStatus.APPROVED, actor="boss", reason="ok"
    )
    with pytest.raises(ValueError):
        workflow.transition(
            "PKG-DEP", "hash-dep", ApprovalStatus.DEPRECATED, actor="boss"
        )
    workflow.transition(
        "PKG-DEP",
        "hash-dep",
        ApprovalStatus.DEPRECATED,
        actor="boss",
        reason="superseded by newer hash",
    )


def test_approval_workflow_blocks_approval_with_acceptance_errors() -> None:
    """Approval mit fehlerhaftem AcceptanceReport muss blocken."""
    workflow = ApprovalWorkflow()
    workflow.register("PKG-AC", "hash-ac")
    workflow.transition("PKG-AC", "hash-ac", ApprovalStatus.VALIDATED, actor="a")
    workflow.transition("PKG-AC", "hash-ac", ApprovalStatus.REVIEWED, actor="b")

    bad_report = AcceptanceReport(package_id="PKG-AC", framework_version="4.2")
    bad_report.findings.append(
        AcceptanceFinding("ACCEPT001", "ERROR", "framework_version missing")
    )

    with pytest.raises(ValueError):
        workflow.transition(
            "PKG-AC",
            "hash-ac",
            ApprovalStatus.APPROVED,
            actor="boss",
            reason="forced",
            acceptance_report=bad_report,
        )


def test_approval_workflow_approve_if_accepted_passes_clean_report() -> None:
    workflow = ApprovalWorkflow()
    workflow.register("PKG-OK", "hash-ok")
    workflow.transition("PKG-OK", "hash-ok", ApprovalStatus.VALIDATED, actor="a")
    workflow.transition("PKG-OK", "hash-ok", ApprovalStatus.REVIEWED, actor="b")

    checker = MetadataAcceptanceChecker(min_datapoints=0, min_templates=0)
    package = MetadataPackage(package_id="PKG-OK", framework_version="4.2")
    report = checker.check(package)
    assert not report.has_errors()

    event = workflow.approve_if_accepted(
        "PKG-OK",
        "hash-ok",
        actor="boss",
        reason="acceptance clean",
        acceptance_report=report,
    )
    assert event.to_status == ApprovalStatus.APPROVED
    assert "acceptance_report" in event.metadata


def test_approval_workflow_rejection_requires_reason() -> None:
    workflow = ApprovalWorkflow()
    workflow.register("PKG-5", "hash-5")
    workflow.transition("PKG-5", "hash-5", ApprovalStatus.VALIDATED, actor="a")
    with pytest.raises(ValueError):
        workflow.transition("PKG-5", "hash-5", ApprovalStatus.REJECTED, actor="reviewer")
    event = workflow.transition(
        "PKG-5", "hash-5", ApprovalStatus.REJECTED, actor="reviewer", reason="missing data"
    )
    assert event.to_status == ApprovalStatus.REJECTED


# --- RuleReview / diff_rules -----------------------------------------------


def _rule(rule_id: str, **overrides) -> RuleDefinitionV2:
    base = dict(
        rule_id=rule_id,
        scope="row",
        target_template="B02.00",
        condition='c0010 = "X"',
        assertion="is_not_null(c0020)",
        severity="ERROR",
        message="missing",
    )
    base.update(overrides)
    return RuleDefinitionV2(**base)


def test_rule_review_registry_fingerprint_distinguishes_versions() -> None:
    rule_v1 = _rule("R1")
    rule_v2 = _rule("R1", assertion="is_not_null(c0030)")

    registry = RuleReviewRegistry()
    registry.upsert(
        rule_v1,
        RuleReview(
            rule_id="R1",
            review_status=RuleReviewStatus.APPROVED,
            test_status=RuleTestStatus.PASSED,
            reviewer="alice",
            positive_tests=1,
            negative_tests=1,
        ),
    )

    assert registry.get(rule_v1) is not None
    assert registry.get(rule_v2) is None  # geänderte Regel braucht neuen Review


def test_rule_review_fingerprint_invalidates_on_message_only_change() -> None:
    """Reine ``message``-Änderung muss Review verwerfen (Konsistenz zu diff_rules)."""
    rule_v1 = _rule("R1", message="alter Hinweis")
    rule_v2 = _rule("R1", message="neuer Hinweis")

    registry = RuleReviewRegistry()
    registry.upsert(
        rule_v1,
        RuleReview(
            rule_id="R1",
            review_status=RuleReviewStatus.APPROVED,
            test_status=RuleTestStatus.PASSED,
        ),
    )

    assert registry.get(rule_v1) is not None
    assert registry.get(rule_v2) is None

    changes = diff_rules([rule_v1], [rule_v2])
    assert changes and changes[0].change_type == "changed"
    assert "message" in changes[0].fields_changed


def test_rule_review_production_ready_filter() -> None:
    r1 = _rule("R1")
    r2 = _rule("R2")
    registry = RuleReviewRegistry()
    registry.upsert(
        r1,
        RuleReview(
            rule_id="R1",
            review_status=RuleReviewStatus.APPROVED,
            test_status=RuleTestStatus.PASSED,
        ),
    )
    registry.upsert(
        r2,
        RuleReview(
            rule_id="R2",
            review_status=RuleReviewStatus.PENDING,
            test_status=RuleTestStatus.MISSING,
        ),
    )

    ready = registry.production_ready_rules([r1, r2])
    assert [r.rule_id for r in ready] == ["R1"]


def test_rule_summary_contains_key_fields() -> None:
    rule = _rule("R1", message="Pflichtfeld c0020")
    summary = rule_summary(rule)
    assert "R1" in summary
    assert "ERROR" in summary
    assert "B02.00" in summary
    assert "c0020" in summary


def test_diff_rules_detects_added_removed_changed() -> None:
    old = [_rule("R1"), _rule("R2")]
    new = [
        _rule("R1", assertion="is_not_null(c0030)"),
        _rule("R3"),
    ]
    changes = diff_rules(old, new)
    rule_ids = {c.rule_id: c for c in changes}
    assert rule_ids["R1"].change_type == "changed"
    assert "assertion" in rule_ids["R1"].fields_changed
    assert rule_ids["R2"].change_type == "removed"
    assert rule_ids["R3"].change_type == "added"


# --- OverrideRegistry ------------------------------------------------------


def test_override_registry_requires_reason_and_author() -> None:
    with pytest.raises(ValueError):
        OverrideEntry(
            override_id="O1",
            override_type=OverrideType.RULE,
            target_id="R1",
            reason="",
            author="alice",
        )
    with pytest.raises(ValueError):
        OverrideEntry(
            override_id="O2",
            override_type=OverrideType.RULE,
            target_id="R1",
            reason="needed",
            author="",
        )


def test_override_registry_activity_window_and_revocation() -> None:
    registry = OverrideRegistry()
    registry.add(
        OverrideEntry(
            override_id="O1",
            override_type=OverrideType.RULE,
            target_id="R1",
            reason="not auto-translatable",
            author="alice",
            valid_from="2026-01-01",
            valid_to="2026-12-31",
        )
    )
    assert registry.find_for_target(OverrideType.RULE, "R1", "2026-06-30")
    assert not registry.find_for_target(OverrideType.RULE, "R1", "2027-01-15")

    registry.revoke("O1", actor="bob", reason="rule now translatable")
    assert not registry.find_for_target(OverrideType.RULE, "R1", "2026-06-30")
    audit = registry.audit_log()
    assert audit and audit[0]["override_id"] == "O1"


def test_override_registry_hides_revoked_without_reporting_date() -> None:
    """Widerrufene Overrides dürfen auch ohne reporting_date nicht erscheinen."""
    registry = OverrideRegistry()
    registry.add(
        OverrideEntry(
            override_id="O1",
            override_type=OverrideType.RULE,
            target_id="R1",
            reason="needed",
            author="alice",
        )
    )
    assert registry.find_for_target(OverrideType.RULE, "R1")
    registry.revoke("O1", actor="bob", reason="no longer needed")
    assert registry.find_for_target(OverrideType.RULE, "R1") == []
    # Audit-Blick mit include_revoked=True liefert beide Modi.
    audit_view = registry.find_for_target(
        OverrideType.RULE, "R1", include_revoked=True
    )
    assert len(audit_view) == 1 and audit_view[0].revoked


def test_override_registry_revoke_requires_reason() -> None:
    registry = OverrideRegistry()
    registry.add(
        OverrideEntry(
            override_id="O1",
            override_type=OverrideType.METADATA,
            target_id="dp-1",
            reason="needed",
            author="a",
        )
    )
    with pytest.raises(ValueError):
        registry.revoke("O1", actor="b", reason="")


# --- ChangeControlReport ---------------------------------------------------


def _empty_delta(**overrides) -> PackageDelta:
    base = dict(
        package_id_old="PKG-1",
        package_id_new="PKG-2",
        framework_version_old="4.1",
        framework_version_new="4.2",
    )
    base.update(overrides)
    return PackageDelta(**base)


def test_change_control_report_aggregates_rule_changes_and_required_approvals() -> None:
    old_pkg = MetadataPackage(package_id="PKG-1", framework_version="4.1")
    new_pkg = MetadataPackage(package_id="PKG-2", framework_version="4.2")
    delta = _empty_delta(
        templates_added=["B02.00"],
        codelists_added=["CL-FUND"],
        rules_added=["R-NEW"],
    )
    new_rule = _rule("R-NEW", metadata={"translatable": False})
    report = build_change_control_report(
        old_pkg, new_pkg, delta, old_rules=[], new_rules=[new_rule]
    )

    assert isinstance(report, ChangeControlReport)
    assert "B02.00" in report.affected_templates
    assert "CL-FUND" in report.affected_codelists
    assert any(c.rule_id == "R-NEW" and c.change_type == "added" for c in report.rule_changes)
    assert "rule_review" in report.required_approvals
    assert "codelist_review" in report.required_approvals
    assert "template_review" in report.required_approvals
    assert any("nicht automatisch übersetzbar" in note for note in report.notes)


def test_change_control_report_without_old_rules_falls_back_to_delta() -> None:
    new_pkg = MetadataPackage(package_id="PKG-2", framework_version="4.2")
    delta = _empty_delta(rules_added=["A"], rules_removed=["B"], rules_changed=["C"])
    report = build_change_control_report(None, new_pkg, delta, old_rules=None, new_rules=[])
    rule_ids = {(c.rule_id, c.change_type) for c in report.rule_changes}
    assert ("A", "added") in rule_ids
    assert ("B", "removed") in rule_ids
    assert ("C", "changed") in rule_ids
