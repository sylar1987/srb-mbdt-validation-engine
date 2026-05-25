"""Phase-4-Governance-Layer.

Stellt Release-Registry, Approval-Workflow, Rule-Review, Override-Registry
und Change-Control für die metadata-getriebene Pipeline aus Phase 3 bereit.
Alles ist bewusst leichtgewichtig (In-Memory plus ``to_dict``-Serialisierung)
und auf Auditierbarkeit, nicht auf produktive Workflow-Engines ausgelegt.
"""

from app.governance.release_registry import (
    ReleaseRegistry,
    ReleaseRecord,
    ReleaseStatus,
)
from app.governance.approval_workflow import (
    AcceptanceReportLike,
    ApprovalWorkflow,
    ApprovalEvent,
    ApprovalStatus,
    NotApprovedError,
)
from app.governance.rule_review import (
    RuleReview,
    RuleReviewRegistry,
    RuleReviewStatus,
    RuleTestStatus,
    rule_summary,
    diff_rules,
)
from app.governance.override_registry import (
    OverrideRegistry,
    OverrideEntry,
    OverrideType,
)
from app.governance.change_control import (
    ChangeControlReport,
    build_change_control_report,
)
from app.governance.engine_gate import EngineGate, GateDecision, GateMode

__all__ = [
    "ReleaseRegistry",
    "ReleaseRecord",
    "ReleaseStatus",
    "AcceptanceReportLike",
    "ApprovalWorkflow",
    "ApprovalEvent",
    "ApprovalStatus",
    "NotApprovedError",
    "RuleReview",
    "RuleReviewRegistry",
    "RuleReviewStatus",
    "RuleTestStatus",
    "rule_summary",
    "diff_rules",
    "OverrideRegistry",
    "OverrideEntry",
    "OverrideType",
    "ChangeControlReport",
    "build_change_control_report",
    "EngineGate",
    "GateDecision",
    "GateMode",
]
