"""ValidationEngine – Orchestriert Setup, System-Checks und Dispatching."""

from __future__ import annotations

from typing import List, Optional

from app.models import ValidationIssue, ValidationSummary
from app.services.reference_date_service import extract_reference_date
from app.validation.context import ValidationContext
from app.validation.dispatcher import Dispatcher
from app.validation.structure_validator import validate_structure


class ValidationEngine:
    """Führt einen kompletten Validierungslauf gegen einen ``ValidationContext`` aus."""

    def __init__(self, dispatcher: Optional[Dispatcher] = None):
        self.dispatcher = dispatcher or Dispatcher()

    def _system_checks(self, ctx: ValidationContext) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        if not ctx.batch.templates:
            issues.append(ValidationIssue(
                rule_id="SYS_001", rule_level="SYSTEM", rule_type="SYSTEM",
                template="ALL", severity="ERROR",
                message="Keine Templates geladen. load_xlsx() oder load_csv_dir() aufrufen.",
            ))
            return issues
        if "B99.00" not in ctx.batch.templates:
            issues.append(ValidationIssue(
                rule_id="SYS_002", rule_level="SYSTEM", rule_type="MANDATORY_TEMPLATE",
                template="B99.00", severity="ERROR",
                message="B99.00 (Identification of the report) fehlt. Pflicht-Template.",
                explanation="Every MBDT submission must include B99.00.",
                dpm_reference="SRB MBDT Guidance §2.1",
            ))
        return issues

    def run(self, ctx: ValidationContext) -> List[ValidationIssue]:
        ctx.issues = []

        sys_issues = self._system_checks(ctx)
        ctx.issues.extend(sys_issues)
        if any(i.rule_id == "SYS_001" for i in sys_issues):
            return ctx.issues

        if not ctx.reference_date:
            rd = extract_reference_date(ctx.batch.templates)
            if rd:
                ctx.reference_date = rd
                ctx.batch.reference_date = rd

        # Phase 1.5: Strukturprüfung gegen field_structure.json
        ctx.issues.extend(validate_structure(ctx))

        # Legacy-Adapter braucht aktuellen Stand
        if ctx.legacy_validator is not None:
            ctx.legacy_validator.errors = []

        self.dispatcher.dispatch_all(ctx)
        return ctx.issues

    @staticmethod
    def summarize(ctx: ValidationContext) -> ValidationSummary:
        return ValidationSummary.from_issues(ctx.issues, ctx.batch.templates.keys())
