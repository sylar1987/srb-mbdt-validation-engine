"""Run-Manifest-Skelett.

Phase 1.5 bereitet die spätere Phase-3-Audit-Schicht vor, ohne ihre
volle Pipeline zu bauen. Jeder Lauf erhält:

* eine deterministische ``run_id`` (UUIDv5 über
  Input-Pfad + Start-Zeitstempel)
* ``started_at`` / ``finished_at``
* ``input_hash`` (SHA-256 über die Rohbytes aller geladenen Quellen,
  alphabetisch sortiert – damit ist das Manifest reproduzierbar)
* Katalog-Metadaten (Version, Regel-Anzahl)
* ``issue_count`` und Severity-Aufschlüsselung

Das Manifest wird als JSON-Datei geschrieben (deterministische Reihenfolge).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.models import InputBatch, ValidationIssue

# Stabiler Namespace für UUIDv5 – beliebig, aber konstant.
_RUN_NAMESPACE = uuid.UUID("3c7f9a1e-8a3f-4ad6-9e6e-2a8b7c8e3a4e")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_path(path: Path) -> str:
    """SHA-256 über Datei- oder Verzeichnisinhalt (rekursiv, sortiert)."""
    if not path.exists():
        return ""
    h = hashlib.sha256()
    if path.is_file():
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        return h.hexdigest()
    for p in sorted(path.rglob("*")):
        if p.is_file():
            rel = p.relative_to(path).as_posix()
            h.update(rel.encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def _summarize_severities(issues: Iterable[ValidationIssue]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for it in issues:
        counts[it.severity] = counts.get(it.severity, 0) + 1
    return counts


def generate_run_id(input_path: str, started_at: str) -> str:
    return str(uuid.uuid5(_RUN_NAMESPACE, f"{input_path}|{started_at}"))


@dataclass
class RunManifest:
    """Audit-Skelett für einen Validierungslauf."""

    run_id: str
    started_at: str
    finished_at: str = ""
    input_path: str = ""
    input_source_type: str = ""
    input_hash: str = ""
    catalog_version: str = ""
    catalog_rule_count: int = 0
    de_annex: bool = False
    issue_count: int = 0
    issue_severities: Dict[str, int] = field(default_factory=dict)
    templates_loaded: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "input": {
                "path": self.input_path,
                "source_type": self.input_source_type,
                "hash": self.input_hash,
            },
            "catalog": {
                "version": self.catalog_version,
                "rule_count": self.catalog_rule_count,
                "de_annex": self.de_annex,
            },
            "templates_loaded": sorted(self.templates_loaded),
            "issues": {
                "count": self.issue_count,
                "by_severity": dict(sorted(self.issue_severities.items())),
            },
        }

    def to_json(self) -> str:
        """Deterministisches JSON (sortierte Keys, kompakter Stil)."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=False)

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json(), encoding="utf-8")
        return target


def build_manifest(
    batch: InputBatch,
    catalog_metadata: Optional[dict],
    catalog_rule_count: int,
    issues: Iterable[ValidationIssue],
    started_at: str,
    finished_at: Optional[str] = None,
    de_annex: bool = False,
    run_id: Optional[str] = None,
) -> RunManifest:
    issues_list = list(issues)
    input_path_str = batch.source_path or ""
    input_hash = _hash_path(Path(input_path_str)) if input_path_str else ""
    rid = run_id or generate_run_id(input_path_str, started_at)
    return RunManifest(
        run_id=rid,
        started_at=started_at,
        finished_at=finished_at or _utc_now_iso(),
        input_path=input_path_str,
        input_source_type=batch.source_type or "",
        input_hash=input_hash,
        catalog_version=str((catalog_metadata or {}).get("version", "")),
        catalog_rule_count=catalog_rule_count,
        de_annex=de_annex,
        issue_count=len(issues_list),
        issue_severities=_summarize_severities(issues_list),
        templates_loaded=list(batch.templates.keys()),
    )
