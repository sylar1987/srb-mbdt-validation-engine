"""Change-Control-Report über Package-Deltas (AP 4.2 / 4.3).

Aggregiert Phase-3-``PackageDelta`` und Phase-4-Regel-/Rule-Review-Stände
zu einem Bericht, der vor einer Freigabe entschieden werden muss.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from app.metadata.metadata_versioning import PackageDelta
from app.models import MetadataPackage, RuleDefinitionV2
from app.governance.rule_review import RuleChange, diff_rules


@dataclass
class ChangeControlReport:
    """Bündelt was sich in einem Package geändert hat und welche Freigaben es braucht."""

    package_id_old: str
    package_id_new: str
    framework_version_old: str
    framework_version_new: str
    delta: PackageDelta
    rule_changes: List[RuleChange] = field(default_factory=list)
    affected_templates: List[str] = field(default_factory=list)
    affected_codelists: List[str] = field(default_factory=list)
    required_approvals: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )

    def has_changes(self) -> bool:
        return (
            self.delta.has_changes()
            or bool(self.rule_changes)
            or bool(self.affected_templates)
            or bool(self.affected_codelists)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id_old": self.package_id_old,
            "package_id_new": self.package_id_new,
            "framework_version_old": self.framework_version_old,
            "framework_version_new": self.framework_version_new,
            "delta": self.delta.to_dict(),
            "rule_changes": [c.to_dict() for c in self.rule_changes],
            "affected_templates": list(self.affected_templates),
            "affected_codelists": list(self.affected_codelists),
            "required_approvals": list(self.required_approvals),
            "notes": list(self.notes),
            "generated_at": self.generated_at,
        }


def _unique_sorted(values: Iterable[str]) -> List[str]:
    return sorted({v for v in values if v})


def build_change_control_report(
    old_pkg: Optional[MetadataPackage],
    new_pkg: MetadataPackage,
    delta: PackageDelta,
    old_rules: Optional[Iterable[RuleDefinitionV2]] = None,
    new_rules: Optional[Iterable[RuleDefinitionV2]] = None,
) -> ChangeControlReport:
    """Erstellt einen ChangeControlReport aus einem PackageDelta.

    ``old_rules`` darf ``None`` sein, wenn das alte Package nicht
    geladen werden konnte; in dem Fall wird der Regelvergleich aus
    ``delta`` übernommen, ohne Detailfelder.
    """
    new_rule_list = list(new_rules or new_pkg.rules)
    if old_rules is not None:
        rule_changes = diff_rules(old_rules, new_rule_list)
    else:
        rule_changes = (
            [RuleChange(rule_id=rid, change_type="added") for rid in delta.rules_added]
            + [RuleChange(rule_id=rid, change_type="removed") for rid in delta.rules_removed]
            + [RuleChange(rule_id=rid, change_type="changed") for rid in delta.rules_changed]
        )

    # Welche Templates / Codelists sind betroffen?
    affected_templates: List[str] = []
    affected_templates.extend(delta.templates_added)
    affected_templates.extend(delta.templates_removed)
    affected_templates.extend(delta.templates_changed)
    # Regeln können Templates anstoßen.
    for change in rule_changes:
        rule = _find_rule(change.rule_id, new_rule_list)
        if rule is not None and rule.target_template:
            affected_templates.append(rule.target_template)

    affected_codelists: List[str] = []
    affected_codelists.extend(delta.codelists_added)
    affected_codelists.extend(delta.codelists_removed)
    affected_codelists.extend(delta.codelists_changed)

    required: List[str] = []
    if rule_changes:
        required.append("rule_review")
    if delta.codelists_added or delta.codelists_removed or delta.codelists_changed:
        required.append("codelist_review")
    if delta.templates_added or delta.templates_removed or delta.templates_changed:
        required.append("template_review")
    if delta.datapoints_added or delta.datapoints_removed or delta.datapoints_changed:
        required.append("datapoint_review")
    if not required and delta.has_changes():
        required.append("package_review")

    notes: List[str] = []
    untranslatable_added = [
        change.rule_id
        for change in rule_changes
        if change.change_type == "added"
        and _is_untranslatable(_find_rule(change.rule_id, new_rule_list))
    ]
    if untranslatable_added:
        notes.append(
            "nicht automatisch übersetzbare Regeln erfordern Override oder manuelle Ergänzung: "
            + ", ".join(sorted(untranslatable_added))
        )

    return ChangeControlReport(
        package_id_old=delta.package_id_old,
        package_id_new=delta.package_id_new,
        framework_version_old=delta.framework_version_old,
        framework_version_new=delta.framework_version_new,
        delta=delta,
        rule_changes=rule_changes,
        affected_templates=_unique_sorted(affected_templates),
        affected_codelists=_unique_sorted(affected_codelists),
        required_approvals=sorted(set(required)),
        notes=notes,
    )


def _find_rule(rule_id: str, rules: Iterable[RuleDefinitionV2]) -> Optional[RuleDefinitionV2]:
    for rule in rules:
        if rule.rule_id == rule_id:
            return rule
    return None


def _is_untranslatable(rule: Optional[RuleDefinitionV2]) -> bool:
    if rule is None:
        return False
    return rule.metadata.get("translatable") is False
