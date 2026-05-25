"""Validiert die exportrelevanten Voraussetzungen vor dem Schreiben."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from app.models import CanonicalFact, MetadataPackage


@dataclass
class ExportValidationIssue:
    fact_id: str
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"fact_id": self.fact_id, "code": self.code, "message": self.message}


class ExportValidator:
    """Technische Plausibilität vor Exportlauf.

    Prüft Pflichtdimensionen, Kontext, Einheiten bei monetary,
    technische Identifier, Dubletten, Metadata-Versionskonsistenz.
    """

    def validate(
        self,
        facts: Iterable[CanonicalFact],
        package: MetadataPackage,
    ) -> List[ExportValidationIssue]:
        issues: List[ExportValidationIssue] = []
        facts = list(facts)

        mandatory_dims = {
            d.dimension_id for d in package.dimensions if d.mandatory
        }
        dp_index = {dp.datapoint_id: dp for dp in package.datapoints}

        seen_keys: dict = {}
        for fact in facts:
            dp = dp_index.get(fact.datapoint_id)
            if dp is None:
                issues.append(
                    ExportValidationIssue(
                        fact.fact_id, "EX001",
                        f"datapoint {fact.datapoint_id} not in metadata",
                    )
                )
                continue

            if not dp.technical_identifier:
                issues.append(
                    ExportValidationIssue(
                        fact.fact_id, "EX002",
                        f"datapoint {dp.datapoint_id} has no technical_identifier",
                    )
                )

            for dim in mandatory_dims & set(dp.dimensions):
                if dim not in fact.dimensions:
                    issues.append(
                        ExportValidationIssue(
                            fact.fact_id, "EX010",
                            f"missing mandatory dimension {dim}",
                        )
                    )

            if not fact.context.reference_date and not fact.context.period_end:
                issues.append(
                    ExportValidationIssue(
                        fact.fact_id, "EX020", "context has no reference period",
                    )
                )

            if dp.data_type.upper() == "MONETARY" and not fact.unit:
                issues.append(
                    ExportValidationIssue(
                        fact.fact_id, "EX030",
                        f"monetary datapoint {dp.datapoint_id} requires unit",
                    )
                )

            if fact.metadata_version != package.framework_version:
                issues.append(
                    ExportValidationIssue(
                        fact.fact_id, "EX040",
                        f"metadata_version {fact.metadata_version} != package version {package.framework_version}",
                    )
                )

            key = (
                fact.template_id,
                fact.field_code,
                fact.context.entity,
                fact.context.reference_date,
                tuple(sorted(fact.dimensions.items())),
            )
            if key in seen_keys:
                issues.append(
                    ExportValidationIssue(
                        fact.fact_id, "EX050",
                        f"duplicate fact for key {key} (other fact {seen_keys[key]})",
                    )
                )
            else:
                seen_keys[key] = fact.fact_id

        return issues
