"""Override-Registry für kontrollierte fachliche Abweichungen (AP 4.3).

Decken die Fälle ab, in denen Regeln nicht automatisch übersetzbar sind
oder eine Metadatenabweichung fachlich gerechtfertigt ist. Jeder Eintrag
benötigt Grund, Autor und Gültigkeitszeitraum — stille Overrides sind
ausgeschlossen.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional


class OverrideType:
    RULE = "rule"
    METADATA = "metadata"
    CODELIST = "codelist"
    TEMPLATE = "template"

    ALL = (RULE, METADATA, CODELIST, TEMPLATE)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


@dataclass
class OverrideEntry:
    """Ein einzelner Override mit Audit-Daten."""

    override_id: str
    override_type: str
    target_id: str  # rule_id / template_id / codelist_id / datapoint_id
    reason: str
    author: str
    valid_from: str = ""
    valid_to: str = ""
    replacement: Dict[str, Any] = field(default_factory=dict)
    revoked: bool = False
    revoked_reason: str = ""
    revoked_by: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.override_type not in OverrideType.ALL:
            raise ValueError(f"unsupported override type '{self.override_type}'")
        if not self.reason:
            raise ValueError("override requires a non-empty reason")
        if not self.author:
            raise ValueError("override requires an author")
        _parse_date(self.valid_from)
        _parse_date(self.valid_to)

    def is_active_on(self, reporting_date: str) -> bool:
        if self.revoked:
            return False
        target = _parse_date(reporting_date)
        if target is None:
            return False
        start = _parse_date(self.valid_from)
        end = _parse_date(self.valid_to)
        if start is not None and target < start:
            return False
        if end is not None and target > end:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OverrideRegistry:
    """Verwaltet ``OverrideEntry`` mit Audit-Trail und Revocation."""

    def __init__(self) -> None:
        self._entries: Dict[str, OverrideEntry] = {}
        self._revocations: List[Dict[str, str]] = []

    def add(self, entry: OverrideEntry) -> OverrideEntry:
        if entry.override_id in self._entries:
            raise ValueError(f"override '{entry.override_id}' already exists")
        self._entries[entry.override_id] = entry
        return entry

    def revoke(self, override_id: str, actor: str, reason: str) -> OverrideEntry:
        if not reason:
            raise ValueError("revocation requires a reason")
        if not actor:
            raise ValueError("revocation requires an actor")
        entry = self._entries.get(override_id)
        if entry is None:
            raise KeyError(f"unknown override '{override_id}'")
        if entry.revoked:
            raise ValueError(f"override '{override_id}' already revoked")
        entry.revoked = True
        entry.revoked_by = actor
        entry.revoked_reason = reason
        self._revocations.append(
            {
                "override_id": override_id,
                "actor": actor,
                "reason": reason,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
            }
        )
        return entry

    def get(self, override_id: str) -> Optional[OverrideEntry]:
        return self._entries.get(override_id)

    def find_for_target(
        self,
        override_type: str,
        target_id: str,
        reporting_date: Optional[str] = None,
        include_revoked: bool = False,
    ) -> List[OverrideEntry]:
        """Sucht Overrides für (override_type, target_id).

        Widerrufene Einträge werden standardmäßig ausgeblendet — auch wenn
        kein ``reporting_date`` übergeben wurde. ``include_revoked=True``
        erlaubt einen expliziten Audit-Blick auf alle (auch widerrufenen)
        Einträge; das ist nie der Default, damit produktive Aufrufer keine
        widerrufene Ausnahme versehentlich anwenden.
        """
        results = [
            entry for entry in self._entries.values()
            if entry.override_type == override_type and entry.target_id == target_id
        ]
        if not include_revoked:
            results = [entry for entry in results if not entry.revoked]
        if reporting_date is not None:
            results = [entry for entry in results if entry.is_active_on(reporting_date)]
        return results

    def all_entries(self) -> List[OverrideEntry]:
        return list(self._entries.values())

    def audit_log(self) -> List[Dict[str, str]]:
        return list(self._revocations)
