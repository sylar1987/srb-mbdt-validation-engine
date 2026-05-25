"""Rule-Review-Lifecycle für ``RuleDefinitionV2`` (AP 4.3).

Bildet je Regel-ID einen Reviewstatus, einen Teststatus und eine
fachlesbare Summary ab. ``diff_rules`` erkennt fachlich relevante
Änderungen zwischen zwei Regelversionen — die Grundlage, um
Regressionstest-Anforderungen automatisch auszulösen.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from app.models import RuleDefinitionV2


class RuleReviewStatus:
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"

    ALL = (PENDING, IN_REVIEW, APPROVED, REJECTED, DEPRECATED)


class RuleTestStatus:
    MISSING = "missing"
    PARTIAL = "partial"
    PASSED = "passed"
    FAILED = "failed"

    ALL = (MISSING, PARTIAL, PASSED, FAILED)


_RULE_COMPARABLE_FIELDS = (
    "scope",
    "target_template",
    "condition",
    "assertion",
    "severity",
    "message",
)


@dataclass
class RuleReview:
    """Reviewstatus einer Regel mit Tests, Reviewer und Begründung."""

    rule_id: str
    review_status: str = RuleReviewStatus.PENDING
    test_status: str = RuleTestStatus.MISSING
    reviewer: str = ""
    notes: str = ""
    positive_tests: int = 0
    negative_tests: int = 0
    test_failures: int = 0
    last_updated: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.review_status not in RuleReviewStatus.ALL:
            raise ValueError(f"unknown review status '{self.review_status}'")
        if self.test_status not in RuleTestStatus.ALL:
            raise ValueError(f"unknown test status '{self.test_status}'")

    def is_production_ready(self) -> bool:
        return (
            self.review_status == RuleReviewStatus.APPROVED
            and self.test_status == RuleTestStatus.PASSED
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RuleReviewRegistry:
    """Hält ``RuleReview``-Objekte je Regel und Regelversion."""

    def __init__(self) -> None:
        # Key: (rule_id, rule_fingerprint) — gleiche Regel-ID kann mit
        # verändertem Body als neue Review-Anforderung auftreten.
        self._reviews: Dict[tuple, RuleReview] = {}

    @staticmethod
    def _fingerprint(rule: RuleDefinitionV2) -> str:
        # Felder synchron zu `_RULE_COMPARABLE_FIELDS` halten: jedes Feld,
        # das `diff_rules` als regressionsrelevant einstuft, muss auch den
        # Review-Fingerprint invalidieren. Andernfalls würde z. B. eine
        # geänderte ``message`` als reportingrelevante Änderung gelten,
        # ohne den bestehenden Review zu verwerfen.
        return "|".join(getattr(rule, name) or "" for name in _RULE_COMPARABLE_FIELDS)

    def upsert(self, rule: RuleDefinitionV2, review: RuleReview) -> RuleReview:
        if review.rule_id != rule.rule_id:
            raise ValueError("rule.rule_id and review.rule_id must match")
        key = (rule.rule_id, self._fingerprint(rule))
        self._reviews[key] = review
        return review

    def get(self, rule: RuleDefinitionV2) -> Optional[RuleReview]:
        return self._reviews.get((rule.rule_id, self._fingerprint(rule)))

    def all_reviews(self) -> List[RuleReview]:
        return list(self._reviews.values())

    def production_ready_rules(self, rules: Iterable[RuleDefinitionV2]) -> List[RuleDefinitionV2]:
        ready: List[RuleDefinitionV2] = []
        for rule in rules:
            review = self.get(rule)
            if review is not None and review.is_production_ready():
                ready.append(rule)
        return ready


def rule_summary(rule: RuleDefinitionV2) -> str:
    """Fachlesbare Kurzform einer Regel.

    Bewusst flach gehalten — der primäre Konsument ist eine Review-Liste,
    nicht ein semantischer Renderer.
    """
    parts: List[str] = []
    target = rule.target_template or "*"
    parts.append(f"[{rule.severity}] {rule.rule_id} ({rule.scope}/{target})")
    if rule.condition:
        parts.append(f"wenn {rule.condition}")
    if rule.assertion:
        parts.append(f"dann {rule.assertion}")
    else:
        parts.append("dann (Existenzprüfung)")
    if rule.message:
        parts.append(f"→ {rule.message}")
    translatable = rule.metadata.get("translatable")
    if translatable is False:
        parts.append("[nicht automatisch übersetzbar]")
    return " | ".join(parts)


@dataclass
class RuleChange:
    rule_id: str
    change_type: str  # added | removed | changed
    fields_changed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def diff_rules(
    old_rules: Iterable[RuleDefinitionV2],
    new_rules: Iterable[RuleDefinitionV2],
) -> List[RuleChange]:
    """Vergleicht zwei Regelmengen und liefert Regressionstest-Anlässe."""
    old_map = {r.rule_id: r for r in old_rules}
    new_map = {r.rule_id: r for r in new_rules}
    changes: List[RuleChange] = []

    for rule_id in sorted(new_map.keys() - old_map.keys()):
        changes.append(RuleChange(rule_id=rule_id, change_type="added"))
    for rule_id in sorted(old_map.keys() - new_map.keys()):
        changes.append(RuleChange(rule_id=rule_id, change_type="removed"))
    for rule_id in sorted(old_map.keys() & new_map.keys()):
        old_rule, new_rule = old_map[rule_id], new_map[rule_id]
        diff_fields = [
            name for name in _RULE_COMPARABLE_FIELDS
            if getattr(old_rule, name) != getattr(new_rule, name)
        ]
        if diff_fields:
            changes.append(
                RuleChange(rule_id=rule_id, change_type="changed", fields_changed=diff_fields)
            )

    return changes
