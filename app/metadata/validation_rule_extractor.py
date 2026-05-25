"""Extrahiert Regeln und überführt sie in ``RuleDefinitionV2``.

Nicht direkt übersetzbare Regeln werden mit ``metadata.translatable=False``
markiert statt verworfen.
"""

from __future__ import annotations

from typing import List

from app.metadata.package_reader import RawPackage
from app.models import RuleDefinitionV2
from app.rules_language.parser import parse as parse_expression


class ValidationRuleExtractor:
    """Liest Regeln aus ``raw.rules_payload`` und liefert ``RuleDefinitionV2``."""

    def extract(self, raw: RawPackage) -> List[RuleDefinitionV2]:
        version = str(raw.manifest.get("framework_version") or "")
        source = raw.location.package_id
        rules: List[RuleDefinitionV2] = []
        payload = raw.rules_payload or {}
        for entry in payload.get("rules", []) or []:
            rule_id = (entry.get("rule_id") or "").strip()
            if not rule_id:
                raw.diagnostics.append("rule missing rule_id, skipped")
                continue
            scope = str(entry.get("scope") or "row").lower()
            if scope not in ("row", "template", "cross"):
                raw.diagnostics.append(
                    f"rule {rule_id} has unsupported scope '{scope}', defaulted to 'row'"
                )
                scope = "row"

            assertion = str(entry.get("assertion") or "")
            condition = str(entry.get("condition") or "")
            translatable = bool(entry.get("translatable", True))

            metadata = {
                "framework_version": version,
                "package_id": source,
                "translatable": translatable,
            }
            if "dpm_reference" in entry:
                metadata["dpm_reference"] = entry["dpm_reference"]
            if "codelist_id" in entry:
                metadata["codelist_id"] = entry["codelist_id"]

            if translatable:
                ok, reason = self._validate_dsl(condition, assertion)
                if not ok:
                    metadata["translatable"] = False
                    metadata["translation_error"] = reason
                    raw.diagnostics.append(
                        f"rule {rule_id} not translatable: {reason}"
                    )

            rules.append(
                RuleDefinitionV2(
                    rule_id=rule_id,
                    scope=scope,
                    target_template=str(entry.get("target_template") or ""),
                    condition=condition if metadata.get("translatable") else "",
                    assertion=assertion if metadata.get("translatable") else "",
                    severity=str(entry.get("severity") or "ERROR").upper(),
                    message=str(entry.get("message") or ""),
                    source=f"dpm:{source}",
                    metadata=metadata,
                )
            )
        return rules

    @staticmethod
    def _validate_dsl(condition: str, assertion: str) -> tuple[bool, str]:
        try:
            if condition:
                parse_expression(condition)
            if assertion:
                parse_expression(assertion)
        except Exception as exc:  # noqa: BLE001 - parser is a closed boundary
            return False, str(exc)
        return True, ""
