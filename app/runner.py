"""Runner – Orchestriert einen kompletten Validierungslauf.

Verkettet IO → Konfiguration → Engine → Reporting. Die CLI in
``app/main.py`` bzw. die Legacy-Datei ``run_validation.py`` nutzen den
``Runner`` als zentralen Einstiegspunkt.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Erlaube Import sowohl als Package (`python -m app.main`) als auch direkt
# vom Repo-Root (`python run_validation.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.catalog_loader import (
    load_catalog,
    load_field_structure,
    load_field_structure_model,
)
from app.io import load_csv_dir, load_single_csv, load_xlsx
from app.models import InputBatch, ValidationSummary
from app.reporting import (
    RunManifest,
    build_manifest,
    build_summary,
    write_excel_report,
    write_issue_excel,
)
from app.reporting.manifest import _utc_now_iso, generate_run_id
from app.settings import EngineSettings
from app.validation import Dispatcher, ValidationContext, ValidationEngine


class Runner:
    def __init__(self, settings: Optional[EngineSettings] = None):
        self.settings = settings or EngineSettings()
        self.catalog = load_catalog(self.settings.catalog_path, de_annex=self.settings.de_annex)
        self.field_structure = load_field_structure(self.settings.field_structure_path)
        self.field_structure_model = load_field_structure_model(
            self.settings.field_structure_path
        )
        self.batch: Optional[InputBatch] = None
        self.context: Optional[ValidationContext] = None
        self.summary: Optional[ValidationSummary] = None
        self.manifest: Optional[RunManifest] = None
        self._started_at: str = ""
        # Legacy-Validator (für Phase-1-Adapter & Excel-Report)
        from mbdt_validator import MBDTValidator  # local import to keep startup cheap

        self._legacy = MBDTValidator(
            catalog_path=self.settings.catalog_path,
            de_annex=self.settings.de_annex,
        )

    # ── Input loading ────────────────────────────────────────────────────
    def load_xlsx(self, filepath: str | Path) -> InputBatch:
        self.batch = load_xlsx(filepath, field_structure=self.field_structure_model)
        self.batch.entity_name = self.settings.entity_name
        self.batch.reference_date = self.settings.reference_date
        return self.batch

    def load_csv_dir(self, directory: str | Path) -> InputBatch:
        self.batch = load_csv_dir(directory, field_structure=self.field_structure_model)
        self.batch.entity_name = self.settings.entity_name
        self.batch.reference_date = self.settings.reference_date
        return self.batch

    def load_single_csv(self, filepath: str | Path, template_id: str) -> InputBatch:
        self.batch = load_single_csv(
            filepath, template_id, field_structure=self.field_structure_model
        )
        self.batch.entity_name = self.settings.entity_name
        self.batch.reference_date = self.settings.reference_date
        return self.batch

    # ── Validation ───────────────────────────────────────────────────────
    def validate(self) -> ValidationSummary:
        if self.batch is None:
            raise RuntimeError("Kein InputBatch geladen – load_xlsx/load_csv_dir/load_single_csv aufrufen.")
        self._started_at = _utc_now_iso()
        run_id = generate_run_id(self.batch.source_path or "", self._started_at)
        self.context = ValidationContext(
            batch=self.batch,
            catalog=self.catalog,
            field_structure=self.field_structure,
            field_structure_model=self.field_structure_model,
            de_annex=self.settings.de_annex,
            reference_date=self.settings.reference_date,
            legacy_validator=self._legacy,
            run_id=run_id,
            use_native_validators=bool(
                self.settings.extra.get("use_native_validators", True)
            ),
        )
        engine = ValidationEngine(Dispatcher())
        engine.run(self.context)
        self.summary = build_summary(self.context.issues, self.batch.templates.keys())
        self.manifest = build_manifest(
            batch=self.batch,
            catalog_metadata=self.catalog.metadata,
            catalog_rule_count=len(self.catalog.rules),
            issues=self.context.issues,
            started_at=self._started_at,
            de_annex=self.settings.de_annex,
            run_id=run_id,
        )
        return self.summary

    def write_manifest(self, output_path: str) -> str:
        """Schreibt das Run-Manifest als deterministisches JSON."""
        if self.manifest is None:
            raise RuntimeError("validate() muss zuerst laufen.")
        return str(self.manifest.write(output_path))

    # ── Reporting ────────────────────────────────────────────────────────
    def write_report(self, output_path: str) -> str:
        """Legacy-Vollreport (umfangreiches Excel-Layout)."""
        if self.context is None:
            raise RuntimeError("validate() muss zuerst laufen.")
        return write_excel_report(
            self._legacy,
            self.context.issues,
            output_path,
            entity_name=self.settings.entity_name,
            reference_date=self.settings.reference_date,
        )

    def write_issue_report(self, output_path: str) -> str:
        """Phase-1.5-Standardpfad: schlanker Issue-/Summary-/Manifest-Report
        ohne Legacy-Validator-Abhängigkeit."""
        if self.context is None:
            raise RuntimeError("validate() muss zuerst laufen.")
        return write_issue_excel(
            self.context.issues,
            output_path,
            summary=self.summary,
            manifest=self.manifest,
        )
