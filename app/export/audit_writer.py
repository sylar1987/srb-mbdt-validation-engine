"""Erzeugt das Audit-Log eines Export-Runs."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

from app.models import CanonicalFact, ExportPackage


class AuditWriter:
    AUDIT_NAME = "audit.json"

    @staticmethod
    def input_hash(payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def write(
        self,
        output_dir: str,
        export_package: ExportPackage,
        facts: Iterable[CanonicalFact],
        extra: Dict[str, Any] | None = None,
    ) -> str:
        os.makedirs(output_dir, exist_ok=True)
        audit_path = os.path.join(output_dir, self.AUDIT_NAME)
        payload: Dict[str, Any] = {
            "run_id": export_package.run_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
            "package_id": export_package.package_id,
            "export_format": export_package.export_format,
            "metadata_version": export_package.metadata_version,
            "rule_version": export_package.rule_version,
            "rule_count": export_package.rule_count,
            "input_hash": export_package.input_hash,
            "fact_count": sum(1 for _ in facts) if not isinstance(facts, list) else len(facts),
            "artifacts": [a.to_dict() for a in export_package.artifacts],
            "validation_issues": list(export_package.validation_issues),
            "status": export_package.status,
        }
        if extra:
            payload["extra"] = dict(extra)
        with open(audit_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return audit_path
