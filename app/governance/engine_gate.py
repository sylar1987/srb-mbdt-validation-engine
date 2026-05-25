"""Engine-Gate: Vorab-Entscheidung für die Validierungs-Engine (AP 4.x).

Bündelt die drei Phase-4-Bausteine, die vor einem produktiven Lauf
ausgewertet werden müssen:

* ``ReleaseRegistry`` — gibt es ein registriertes, freigegebenes Release
  für den Reporting-Stichtag und das Framework?
* ``ApprovalWorkflow`` — ist genau dieses Package (über ``content_hash``)
  freigegeben?
* ``MetadataAcceptanceChecker`` — erfüllt das Paket die harten
  Mindestanforderungen (kein Codelist-Drift, Minima erfüllt)?

Das Gate ist bewusst noch **nicht** in ``ValidationEngine.run`` verdrahtet
— das wäre eine Phase-3-tiefe Veränderung. Stattdessen liefert es eine
klare Entscheidung (``allowed`` / ``blocked``), die ein Aufrufer (Engine,
Runner, Service) als Hard- oder Warn-Gate einsetzen kann. Im ``warn``-
Modus wird die Entscheidung auditierbar in ``warnings`` festgehalten,
aber nicht durchgesetzt — niemals stillschweigend.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.governance.approval_workflow import ApprovalStatus, ApprovalWorkflow
from app.governance.release_registry import ReleaseRecord, ReleaseRegistry, ReleaseStatus
from app.quality.metadata_acceptance import (
    AcceptanceReport,
    MetadataAcceptanceChecker,
)


class GateMode:
    """Wie streng das Gate eine Verletzung behandelt."""

    ENFORCE = "enforce"
    WARN = "warn"

    ALL = (ENFORCE, WARN)


@dataclass
class GateDecision:
    """Ergebnis eines Gate-Aufrufs.

    ``allowed=True`` heißt: alle harten Bedingungen sind erfüllt **oder**
    der Modus ist ``warn`` und Verletzungen wurden als Warnung
    protokolliert. ``allowed=False`` tritt nur in ``enforce`` auf.
    """

    allowed: bool
    mode: str
    package_id: str
    content_hash: str
    framework_version: str = ""
    reporting_date: str = ""
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    release: Optional[Dict[str, Any]] = None
    acceptance_report: Optional[Dict[str, Any]] = None
    decided_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EngineGate:
    """Service-Fassade über Release, Approval und Acceptance.

    Konservative Default-Einstellung ``GateMode.ENFORCE``: das Gate
    blockiert, sobald eine Bedingung verletzt ist. Im ``warn``-Modus wird
    weitergeleitet, alle Findings landen in ``decision.warnings`` und
    sind über ``decisions()`` jederzeit auditierbar.
    """

    def __init__(
        self,
        release_registry: ReleaseRegistry,
        approval_workflow: ApprovalWorkflow,
        acceptance_checker: Optional[MetadataAcceptanceChecker] = None,
        default_mode: str = GateMode.ENFORCE,
    ) -> None:
        if default_mode not in GateMode.ALL:
            raise ValueError(f"unsupported gate mode '{default_mode}'")
        self._releases = release_registry
        self._approvals = approval_workflow
        self._acceptance = acceptance_checker or MetadataAcceptanceChecker()
        self._default_mode = default_mode
        self._decisions: List[GateDecision] = []

    def evaluate(
        self,
        package: Any,
        reporting_date: str = "",
        mode: Optional[str] = None,
        kind: str = "package",
    ) -> GateDecision:
        """Beurteilt einen Paketkandidaten gegen Release/Approval/Acceptance.

        Erwartet ein Objekt mit ``package_id``, ``framework_version`` und
        — wenn vorhanden — ``content_hash()``. Akzeptiert auch
        ``MetadataPackage``-Instanzen aus Phase 3.
        """
        if mode is None:
            mode = self._default_mode
        if mode not in GateMode.ALL:
            raise ValueError(f"unsupported gate mode '{mode}'")

        package_id = getattr(package, "package_id", "") or ""
        framework_version = getattr(package, "framework_version", "") or ""
        content_hash_fn = getattr(package, "content_hash", None)
        if callable(content_hash_fn):
            content_hash = content_hash_fn()
        else:
            content_hash = getattr(package, "content_hash", "") or ""

        reasons: List[str] = []
        warnings: List[str] = []

        # 1) Release-Resolve. Wenn ``reporting_date`` leer ist, überspringen
        # wir den Resolve und prüfen rein Approval/Acceptance — das ist der
        # Pfad für reine Package-Freigabe-Checks ohne Reporting-Kontext.
        release_dict: Optional[Dict[str, Any]] = None
        if reporting_date:
            try:
                release: ReleaseRecord = self._releases.resolve(
                    kind=kind,
                    reporting_date=reporting_date,
                    framework_version=framework_version,
                    require_approved=True,
                )
                release_dict = release.to_dict()
                if release.status != ReleaseStatus.APPROVED:
                    reasons.append(
                        f"release '{release.release_id}' has status "
                        f"'{release.status}', not 'approved'"
                    )
                if content_hash and release.content_hash and release.content_hash != content_hash:
                    reasons.append(
                        f"package content_hash '{content_hash}' does not match "
                        f"release '{release.release_id}' content_hash "
                        f"'{release.content_hash}'"
                    )
            except LookupError as exc:
                reasons.append(f"no approved release: {exc}")

        # 2) Approval-Status zum content_hash.
        if not content_hash:
            reasons.append("package has no content_hash; cannot check approval")
        else:
            current = self._approvals.status(package_id, content_hash)
            if current != ApprovalStatus.APPROVED:
                reasons.append(
                    f"package {package_id}@{content_hash} not approved "
                    f"(current status: {current or 'unknown'})"
                )

        # 3) Acceptance-Check — sammelt Errors (hart) und Warnings (weich).
        acceptance_dict: Optional[Dict[str, Any]] = None
        try:
            acceptance: AcceptanceReport = self._acceptance.check(package)
            acceptance_dict = acceptance.to_dict()
            if acceptance.has_errors():
                reasons.append(
                    f"acceptance gate has {acceptance_dict['error_count']} "
                    f"errors"
                )
            if acceptance_dict["warning_count"]:
                warnings.append(
                    f"acceptance gate has {acceptance_dict['warning_count']} "
                    f"warnings"
                )
        except Exception as exc:  # noqa: BLE001 - wir wollen ein klares Finding
            reasons.append(f"acceptance check failed: {exc}")

        allowed = not reasons or mode == GateMode.WARN
        if mode == GateMode.WARN and reasons:
            # In Warn-Mode wandern Reasons in Warnings, bleiben aber
            # sichtbar und werden nicht stillgeschluckt.
            warnings = warnings + [f"WARN-ONLY: {r}" for r in reasons]
            reasons = []

        decision = GateDecision(
            allowed=allowed,
            mode=mode,
            package_id=package_id,
            content_hash=content_hash,
            framework_version=framework_version,
            reporting_date=reporting_date,
            reasons=reasons,
            warnings=warnings,
            release=release_dict,
            acceptance_report=acceptance_dict,
        )
        self._decisions.append(decision)
        return decision

    def decisions(self) -> List[GateDecision]:
        return list(self._decisions)


__all__ = ["EngineGate", "GateDecision", "GateMode"]
