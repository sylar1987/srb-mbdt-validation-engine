"""Approval-Workflow für Metadaten- und Regelstände (AP 4.2).

Statusmodell: ``imported`` → ``validated`` → ``reviewed`` →
``approved`` (oder ``rejected``). ``deprecated`` markiert frühere
Stände. Übergänge sind explizit erlaubt; alles andere wirft.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class ApprovalStatus:
    IMPORTED = "imported"
    VALIDATED = "validated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"

    ALL = (IMPORTED, VALIDATED, REVIEWED, APPROVED, REJECTED, DEPRECATED)


# Erlaubte Übergänge — wir bleiben streng, damit "Black-Box-Freigaben"
# auffallen. Rejection ist aus jedem Vor-Approval-Status möglich;
# Deprecation greift nur nach Approval.
_ALLOWED_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    ApprovalStatus.IMPORTED: (ApprovalStatus.VALIDATED, ApprovalStatus.REJECTED),
    ApprovalStatus.VALIDATED: (ApprovalStatus.REVIEWED, ApprovalStatus.REJECTED),
    ApprovalStatus.REVIEWED: (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED),
    ApprovalStatus.APPROVED: (ApprovalStatus.DEPRECATED,),
    ApprovalStatus.REJECTED: (),
    ApprovalStatus.DEPRECATED: (),
}


class NotApprovedError(RuntimeError):
    """Wird geworfen, wenn produktive Nutzung ohne Freigabe versucht wird."""


@dataclass
class ApprovalEvent:
    """Ein Audit-Eintrag im Freigabeprozess."""

    package_id: str
    content_hash: str
    from_status: str
    to_status: str
    actor: str
    reason: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ApprovalWorkflow:
    """Hält Status je (package_id, content_hash) und protokolliert Events.

    Hash-Kopplung verhindert, dass eine Freigabe ohne Neu-Review still
    auf einen geänderten Stand mitwandert — eine Phase-4-Kernanforderung.
    """

    def __init__(self) -> None:
        self._status: Dict[Tuple[str, str], str] = {}
        self._events: List[ApprovalEvent] = []

    def register(self, package_id: str, content_hash: str) -> str:
        key = (package_id, content_hash)
        if key in self._status:
            raise ValueError(f"package {package_id}@{content_hash} already tracked")
        self._status[key] = ApprovalStatus.IMPORTED
        self._events.append(
            ApprovalEvent(
                package_id=package_id,
                content_hash=content_hash,
                from_status="",
                to_status=ApprovalStatus.IMPORTED,
                actor="system",
                reason="initial import",
            )
        )
        return ApprovalStatus.IMPORTED

    def transition(
        self,
        package_id: str,
        content_hash: str,
        new_status: str,
        actor: str,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        acceptance_report: Optional[Any] = None,
    ) -> ApprovalEvent:
        if new_status not in ApprovalStatus.ALL:
            raise ValueError(f"unsupported approval status '{new_status}'")
        key = (package_id, content_hash)
        current = self._status.get(key)
        if current is None:
            raise KeyError(f"package {package_id}@{content_hash} not registered")
        allowed = _ALLOWED_TRANSITIONS.get(current, ())
        if new_status not in allowed:
            raise ValueError(
                f"illegal transition {current} → {new_status} for {package_id}@{content_hash}; "
                f"allowed: {allowed}"
            )
        # Reason ist Pflicht für nachvollziehbare Endzustände — inkl.
        # DEPRECATED, damit auch das Außerkraftsetzen begründet wird.
        if new_status in (
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.DEPRECATED,
        ) and not reason:
            raise ValueError(f"transition to '{new_status}' requires a reason")
        if not actor:
            raise ValueError("actor is required for approval transitions")

        merged_metadata: Dict[str, Any] = dict(metadata or {})

        # Acceptance-Gate: wenn die Transition zu APPROVED erfolgt und ein
        # ``acceptance_report`` mitgegeben wurde, müssen dessen Errors
        # leer sein. Damit lässt sich der MetadataAcceptanceChecker direkt
        # an den Approval-Schritt koppeln. Ohne Report bleibt das
        # Verhalten kompatibel — die Verantwortung liegt dann beim Caller
        # (siehe Convenience ``approve_if_accepted``).
        if new_status == ApprovalStatus.APPROVED and acceptance_report is not None:
            has_errors = getattr(acceptance_report, "has_errors", None)
            if callable(has_errors) and has_errors():
                raise ValueError(
                    f"approval blocked for {package_id}@{content_hash}: "
                    f"acceptance report has errors"
                )
            to_dict = getattr(acceptance_report, "to_dict", None)
            if callable(to_dict):
                merged_metadata.setdefault("acceptance_report", to_dict())

        event = ApprovalEvent(
            package_id=package_id,
            content_hash=content_hash,
            from_status=current,
            to_status=new_status,
            actor=actor,
            reason=reason,
            metadata=merged_metadata,
        )
        self._status[key] = new_status
        self._events.append(event)
        return event

    def approve_if_accepted(
        self,
        package_id: str,
        content_hash: str,
        actor: str,
        reason: str,
        acceptance_report: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ApprovalEvent:
        """Convenience: nur freigeben, wenn der Acceptance-Report ok ist.

        Wirft ``ValueError``, wenn der Report Errors enthält, und macht das
        Acceptance-Gate damit zu einem expliziten Codeschritt statt zu
        einer reinen Doku-Aussage.
        """
        if acceptance_report is None:
            raise ValueError("approve_if_accepted requires an acceptance_report")
        return self.transition(
            package_id=package_id,
            content_hash=content_hash,
            new_status=ApprovalStatus.APPROVED,
            actor=actor,
            reason=reason,
            metadata=metadata,
            acceptance_report=acceptance_report,
        )

    # -- queries ----------------------------------------------------------
    def status(self, package_id: str, content_hash: str) -> Optional[str]:
        return self._status.get((package_id, content_hash))

    def is_approved(self, package_id: str, content_hash: str) -> bool:
        return self.status(package_id, content_hash) == ApprovalStatus.APPROVED

    def ensure_approved(self, package_id: str, content_hash: str) -> None:
        """Hard-Gate für produktive Nutzung — niemals stillschweigend passieren lassen."""
        current = self.status(package_id, content_hash)
        if current != ApprovalStatus.APPROVED:
            raise NotApprovedError(
                f"package {package_id}@{content_hash} not approved "
                f"(current status: {current or 'unknown'})"
            )

    def events_for(self, package_id: str, content_hash: Optional[str] = None) -> List[ApprovalEvent]:
        return [
            event for event in self._events
            if event.package_id == package_id
            and (content_hash is None or event.content_hash == content_hash)
        ]

    def all_events(self) -> List[ApprovalEvent]:
        return list(self._events)
