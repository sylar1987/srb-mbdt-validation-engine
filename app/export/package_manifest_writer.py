"""Erzeugt das Manifest des Exportpakets (audit-fähig)."""

from __future__ import annotations

import json
import os
from typing import List

from app.models import ExportArtifact, ExportPackage


class PackageManifestWriter:
    MANIFEST_NAME = "manifest.json"

    def write(
        self,
        output_dir: str,
        export_package: ExportPackage,
        additional_artifacts: List[ExportArtifact] | None = None,
    ) -> str:
        os.makedirs(output_dir, exist_ok=True)
        manifest_path = os.path.join(output_dir, self.MANIFEST_NAME)

        all_artifacts = list(export_package.artifacts) + list(additional_artifacts or [])

        payload = {
            "package_id": export_package.package_id,
            "export_format": export_package.export_format,
            "metadata_version": export_package.metadata_version,
            "rule_version": export_package.rule_version,
            "rule_count": export_package.rule_count,
            "input_hash": export_package.input_hash,
            "run_id": export_package.run_id,
            "created_at": export_package.created_at,
            "fact_count": len(export_package.facts),
            "status": export_package.status,
            "validation_issues": list(export_package.validation_issues),
            "artifacts": [a.to_dict() for a in all_artifacts],
        }
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return manifest_path
