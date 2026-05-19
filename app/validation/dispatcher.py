"""Dispatcher – verteilt Regeln an die passenden Validatoren.

In Phase 1 ist das Routing bewusst nach ``rule_level`` strukturiert.
Jeder Validator bringt eine eigene ``handles``-Funktion mit, sodass spätere
Erweiterungen (z. B. neue Regelklassen) ohne Änderungen am Dispatcher
möglich sind.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Sequence

from app.models import RuleDefinition, ValidationIssue
from app.validation import (
    codelist_validator,
    consistency_validator,
    cross_template_validator,
    datatype_validator,
    dq_validator,
    mandatory_validator,
)
from app.validation.context import ValidationContext

ValidatorFn = Callable[[ValidationContext, RuleDefinition], List[ValidationIssue]]
HandlesFn = Callable[[RuleDefinition], bool]


@dataclass
class ValidatorRegistration:
    name: str
    handles: HandlesFn
    run: ValidatorFn


DEFAULT_VALIDATORS: Sequence[ValidatorRegistration] = (
    ValidatorRegistration("mandatory", mandatory_validator.handles, mandatory_validator.validate),
    ValidatorRegistration("codelist", codelist_validator.handles, codelist_validator.validate),
    ValidatorRegistration("datatype", datatype_validator.handles, datatype_validator.validate),
    ValidatorRegistration("consistency", consistency_validator.handles, consistency_validator.validate),
    ValidatorRegistration("cross_template", cross_template_validator.handles, cross_template_validator.validate),
    ValidatorRegistration("dq", dq_validator.handles, dq_validator.validate),
)


class Dispatcher:
    def __init__(self, registrations: Sequence[ValidatorRegistration] = DEFAULT_VALIDATORS):
        self.registrations = list(registrations)

    def dispatch_rule(
        self, ctx: ValidationContext, rule: RuleDefinition
    ) -> List[ValidationIssue]:
        for reg in self.registrations:
            if reg.handles(rule):
                return reg.run(ctx, rule)
        return []

    def dispatch_all(self, ctx: ValidationContext) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        for rule in ctx.rules:
            if rule.de_only and not ctx.de_annex:
                continue
            issues.extend(self.dispatch_rule(ctx, rule))
        ctx.issues.extend(issues)
        return issues
