"""Fachliche Summary aus ``ValidationIssue``-Liste aufbauen."""

from __future__ import annotations

from typing import Iterable, List

from app.models import ValidationIssue, ValidationSummary


def build_summary(
    issues: Iterable[ValidationIssue], templates_validated: Iterable[str]
) -> ValidationSummary:
    return ValidationSummary.from_issues(list(issues), list(templates_validated))
