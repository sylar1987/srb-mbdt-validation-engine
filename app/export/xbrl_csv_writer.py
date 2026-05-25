"""Serialisiert ``CanonicalFact``-Listen als xBRL-CSV-Paket.

MVP: erzeugt ein Verzeichnis mit ``facts.csv`` (Fakten),
``metadata.json`` (Paket-Metadaten) und ``parameters.csv`` (Run-Parameter).
Das Layout ist eine vereinfachte Annäherung an das echte xBRL-CSV-Format;
Ziel ist Anschlussfähigkeit, nicht 1:1-Konformität.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Iterable, List

from app.models import CanonicalFact, ExportArtifact, MetadataPackage


@dataclass
class XbrlCsvResult:
    directory: str
    artifacts: List[ExportArtifact]


class XbrlCsvWriter:
    FACTS_FILENAME = "facts.csv"
    METADATA_FILENAME = "metadata.json"
    PARAMETERS_FILENAME = "parameters.csv"

    def write(
        self,
        output_dir: str,
        facts: Iterable[CanonicalFact],
        package: MetadataPackage,
        run_id: str = "",
    ) -> XbrlCsvResult:
        os.makedirs(output_dir, exist_ok=True)
        facts = list(facts)

        dp_index = {dp.datapoint_id: dp for dp in package.datapoints}

        # Stable, sorted dimension-id set across all facts.
        dim_ids = sorted({d for f in facts for d in f.dimensions.keys()})

        facts_path = os.path.join(output_dir, self.FACTS_FILENAME)
        with open(facts_path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter=",", lineterminator="\n")
            header = [
                "fact_id",
                "datapoint_id",
                "qname",
                "template_id",
                "field_code",
                "value",
                "data_type",
                "unit",
                "entity",
                "reference_date",
                "period_start",
                "period_end",
            ] + [f"dim_{d}" for d in dim_ids]
            writer.writerow(header)
            for f in facts:
                dp = dp_index.get(f.datapoint_id)
                qname = dp.technical_identifier if dp else ""
                row = [
                    f.fact_id,
                    f.datapoint_id,
                    qname,
                    f.template_id,
                    f.field_code,
                    "" if f.value is None else f.value,
                    f.data_type,
                    f.unit,
                    f.context.entity,
                    f.context.reference_date,
                    f.context.period_start,
                    f.context.period_end,
                ]
                row.extend(f.dimensions.get(d, "") for d in dim_ids)
                writer.writerow(row)

        metadata_path = os.path.join(output_dir, self.METADATA_FILENAME)
        metadata_payload = {
            "framework_version": package.framework_version,
            "package_id": package.package_id,
            "metadata_version": package.framework_version,
            "fact_count": len(facts),
            "run_id": run_id,
        }
        with open(metadata_path, "w", encoding="utf-8") as fh:
            json.dump(metadata_payload, fh, indent=2, ensure_ascii=False)

        params_path = os.path.join(output_dir, self.PARAMETERS_FILENAME)
        with open(params_path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter=",", lineterminator="\n")
            writer.writerow(["name", "value"])
            writer.writerow(["framework_version", package.framework_version])
            writer.writerow(["package_id", package.package_id])
            writer.writerow(["run_id", run_id])
            writer.writerow(["fact_count", len(facts)])

        artifacts = [
            self._artifact(facts_path, "text/csv"),
            self._artifact(metadata_path, "application/json"),
            self._artifact(params_path, "text/csv"),
        ]
        return XbrlCsvResult(directory=output_dir, artifacts=artifacts)

    @staticmethod
    def _artifact(path: str, content_type: str) -> ExportArtifact:
        with open(path, "rb") as fh:
            data = fh.read()
        return ExportArtifact(
            filename=os.path.basename(path),
            content_type=content_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
