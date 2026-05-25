"""Delta-Analyse zwischen zwei ``MetadataPackage``-Ständen."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.models import (
    CodelistDefinition,
    DataPointDefinition,
    MetadataPackage,
    RuleDefinitionV2,
    TemplateDefinition,
)


@dataclass
class PackageDelta:
    """Strukturierter Vergleichsbericht zweier Packages."""

    package_id_old: str
    package_id_new: str
    framework_version_old: str
    framework_version_new: str

    datapoints_added: List[str] = field(default_factory=list)
    datapoints_removed: List[str] = field(default_factory=list)
    datapoints_changed: List[str] = field(default_factory=list)

    templates_added: List[str] = field(default_factory=list)
    templates_removed: List[str] = field(default_factory=list)
    templates_changed: List[str] = field(default_factory=list)

    codelists_added: List[str] = field(default_factory=list)
    codelists_removed: List[str] = field(default_factory=list)
    codelists_changed: List[str] = field(default_factory=list)
    codelists_value_diff: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)

    rules_added: List[str] = field(default_factory=list)
    rules_removed: List[str] = field(default_factory=list)
    rules_changed: List[str] = field(default_factory=list)

    def has_changes(self) -> bool:
        return any(
            [
                self.datapoints_added, self.datapoints_removed, self.datapoints_changed,
                self.templates_added, self.templates_removed, self.templates_changed,
                self.codelists_added, self.codelists_removed, self.codelists_changed,
                self.rules_added, self.rules_removed, self.rules_changed,
            ]
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "package_id_old": self.package_id_old,
            "package_id_new": self.package_id_new,
            "framework_version_old": self.framework_version_old,
            "framework_version_new": self.framework_version_new,
            "datapoints": {
                "added": list(self.datapoints_added),
                "removed": list(self.datapoints_removed),
                "changed": list(self.datapoints_changed),
            },
            "templates": {
                "added": list(self.templates_added),
                "removed": list(self.templates_removed),
                "changed": list(self.templates_changed),
            },
            "codelists": {
                "added": list(self.codelists_added),
                "removed": list(self.codelists_removed),
                "changed": list(self.codelists_changed),
                "value_diff": dict(self.codelists_value_diff),
            },
            "rules": {
                "added": list(self.rules_added),
                "removed": list(self.rules_removed),
                "changed": list(self.rules_changed),
            },
        }


class MetadataVersioning:
    """Erzeugt ``PackageDelta`` aus zwei Packages."""

    def diff(self, old: MetadataPackage, new: MetadataPackage) -> PackageDelta:
        delta = PackageDelta(
            package_id_old=old.package_id,
            package_id_new=new.package_id,
            framework_version_old=old.framework_version,
            framework_version_new=new.framework_version,
        )

        self._diff_datapoints(old.datapoints, new.datapoints, delta)
        self._diff_templates(old.templates, new.templates, delta)
        self._diff_codelists(old.codelists, new.codelists, delta)
        self._diff_rules(old.rules, new.rules, delta)
        return delta

    @staticmethod
    def _diff_datapoints(
        old: List[DataPointDefinition],
        new: List[DataPointDefinition],
        delta: PackageDelta,
    ) -> None:
        old_map = {d.datapoint_id: d for d in old}
        new_map = {d.datapoint_id: d for d in new}
        for dp_id in sorted(set(new_map) - set(old_map)):
            delta.datapoints_added.append(dp_id)
        for dp_id in sorted(set(old_map) - set(new_map)):
            delta.datapoints_removed.append(dp_id)
        for dp_id in sorted(set(old_map) & set(new_map)):
            if old_map[dp_id].to_dict() != new_map[dp_id].to_dict():
                delta.datapoints_changed.append(dp_id)

    @staticmethod
    def _diff_templates(
        old: List[TemplateDefinition],
        new: List[TemplateDefinition],
        delta: PackageDelta,
    ) -> None:
        old_map = {t.template_id: t for t in old}
        new_map = {t.template_id: t for t in new}
        for tpl in sorted(set(new_map) - set(old_map)):
            delta.templates_added.append(tpl)
        for tpl in sorted(set(old_map) - set(new_map)):
            delta.templates_removed.append(tpl)
        for tpl in sorted(set(old_map) & set(new_map)):
            if old_map[tpl].to_dict() != new_map[tpl].to_dict():
                delta.templates_changed.append(tpl)

    @staticmethod
    def _diff_codelists(
        old: List[CodelistDefinition],
        new: List[CodelistDefinition],
        delta: PackageDelta,
    ) -> None:
        old_map = {c.codelist_id: c for c in old}
        new_map = {c.codelist_id: c for c in new}
        for cl in sorted(set(new_map) - set(old_map)):
            delta.codelists_added.append(cl)
        for cl in sorted(set(old_map) - set(new_map)):
            delta.codelists_removed.append(cl)
        for cl in sorted(set(old_map) & set(new_map)):
            old_vals = set(old_map[cl].values)
            new_vals = set(new_map[cl].values)
            if old_vals != new_vals or old_map[cl].to_dict() != new_map[cl].to_dict():
                delta.codelists_changed.append(cl)
                delta.codelists_value_diff[cl] = {
                    "added": sorted(new_vals - old_vals),
                    "removed": sorted(old_vals - new_vals),
                }

    @staticmethod
    def _diff_rules(
        old: List[RuleDefinitionV2],
        new: List[RuleDefinitionV2],
        delta: PackageDelta,
    ) -> None:
        old_map = {r.rule_id: r for r in old}
        new_map = {r.rule_id: r for r in new}
        for rid in sorted(set(new_map) - set(old_map)):
            delta.rules_added.append(rid)
        for rid in sorted(set(old_map) - set(new_map)):
            delta.rules_removed.append(rid)
        for rid in sorted(set(old_map) & set(new_map)):
            if old_map[rid].to_dict() != new_map[rid].to_dict():
                delta.rules_changed.append(rid)
