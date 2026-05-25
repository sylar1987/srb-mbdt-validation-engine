"""Minimaler Generator für Rule-Test-Anforderungen (AP 4.3 / AP 4.6).

Verbindet ``RuleDefinitionV2`` mit dem Phase-4-Review-Lifecycle, indem
für jede Regel mindestens ein Positiv- und ein Negativtest gefordert
wird. Der MVP generiert *Anforderungen*, keine ausführbaren Tests —
das vermeidet falsche Sicherheit durch Mock-Daten.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List

from app.models import RuleDefinitionV2


@dataclass
class RuleTestRequirement:
    rule_id: str
    test_type: str  # positive | negative
    description: str
    target_template: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def generate_rule_test_requirements(
    rules: Iterable[RuleDefinitionV2],
) -> List[RuleTestRequirement]:
    requirements: List[RuleTestRequirement] = []
    for rule in rules:
        translatable = rule.metadata.get("translatable")
        if translatable is False:
            requirements.append(
                RuleTestRequirement(
                    rule_id=rule.rule_id,
                    test_type="manual",
                    description=(
                        f"manuelle Testabdeckung für nicht übersetzbare Regel "
                        f"({rule.target_template or '*'})"
                    ),
                    target_template=rule.target_template,
                    metadata={"reason": "untranslatable"},
                )
            )
            continue

        requirements.append(
            RuleTestRequirement(
                rule_id=rule.rule_id,
                test_type="positive",
                description=(
                    "Datensatz erfüllt condition und assertion, kein Issue erwartet"
                ),
                target_template=rule.target_template,
            )
        )
        requirements.append(
            RuleTestRequirement(
                rule_id=rule.rule_id,
                test_type="negative",
                description=(
                    "Datensatz erfüllt condition, verletzt assertion, Issue erwartet"
                ),
                target_template=rule.target_template,
            )
        )
        if rule.condition:
            requirements.append(
                RuleTestRequirement(
                    rule_id=rule.rule_id,
                    test_type="positive",
                    description=(
                        "Datensatz verletzt condition, Regel nicht anwendbar, kein Issue erwartet"
                    ),
                    target_template=rule.target_template,
                    metadata={"variant": "condition_false"},
                )
            )

    return requirements
