"""Release Registry für Framework-, Package-, Rule- und Export-Versionen.

Phase-4-Arbeitspaket 4.1: Mehrversionenfähigkeit. Pakete werden mit
Gültigkeitsfenster registriert und können deterministisch nach
Reporting-Stichtag aufgelöst werden.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional


VALID_KINDS = ("framework", "package", "rule", "export")


class ReleaseStatus:
    DRAFT = "draft"
    REGISTERED = "registered"
    APPROVED = "approved"
    DEPRECATED = "deprecated"

    ALL = (DRAFT, REGISTERED, APPROVED, DEPRECATED)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


@dataclass
class ReleaseRecord:
    """Ein registriertes Release-Artefakt.

    ``kind`` trennt Framework- von Package-/Rule-/Exportversionen, damit
    eine Engine je Reporting-Lauf mehrere Achsen zugleich auflösen kann.
    """

    release_id: str
    kind: str  # framework | package | rule | export
    version: str
    content_hash: str = ""
    framework_version: str = ""
    valid_from: str = ""
    valid_to: str = ""
    status: str = ReleaseStatus.REGISTERED
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )

    def __post_init__(self) -> None:
        if self.kind not in VALID_KINDS:
            raise ValueError(f"unsupported release kind '{self.kind}'; allowed {VALID_KINDS}")
        if self.status not in ReleaseStatus.ALL:
            raise ValueError(f"unsupported release status '{self.status}'")
        _parse_date(self.valid_from)
        _parse_date(self.valid_to)

    def covers(self, reporting_date: str) -> bool:
        """Prüft, ob ``reporting_date`` im Gültigkeitsfenster liegt."""
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

    def is_active(self) -> bool:
        return self.status in (ReleaseStatus.REGISTERED, ReleaseStatus.APPROVED)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReleaseRegistry:
    """In-Memory-Registry mit deterministischer Auflösung pro Stichtag.

    Die Registry erzwingt Eindeutigkeit über ``release_id`` und prüft bei
    überlappenden Gültigkeitsfenstern derselben (kind, framework_version),
    damit kein Reporting-Stichtag mehrdeutig auflöst.
    """

    def __init__(self) -> None:
        self._records: Dict[str, ReleaseRecord] = {}

    # -- registration -----------------------------------------------------
    def register(self, record: ReleaseRecord) -> ReleaseRecord:
        if record.release_id in self._records:
            raise ValueError(f"release '{record.release_id}' already registered")
        self._check_no_overlap(record)
        self._records[record.release_id] = record
        return record

    def _check_no_overlap(self, candidate: ReleaseRecord) -> None:
        for existing in self._records.values():
            if existing.kind != candidate.kind:
                continue
            if existing.framework_version and candidate.framework_version:
                if existing.framework_version != candidate.framework_version:
                    continue
            if not existing.is_active():
                continue
            if _intervals_overlap(existing, candidate):
                raise ValueError(
                    f"release '{candidate.release_id}' overlaps with active "
                    f"release '{existing.release_id}' for kind '{candidate.kind}'"
                )

    # -- mutation ---------------------------------------------------------
    def set_status(self, release_id: str, new_status: str) -> ReleaseRecord:
        if new_status not in ReleaseStatus.ALL:
            raise ValueError(f"unsupported release status '{new_status}'")
        record = self._must_get(release_id)
        record.status = new_status
        return record

    def deprecate(self, release_id: str) -> ReleaseRecord:
        return self.set_status(release_id, ReleaseStatus.DEPRECATED)

    # -- queries ----------------------------------------------------------
    def get(self, release_id: str) -> Optional[ReleaseRecord]:
        return self._records.get(release_id)

    def list(self, kind: Optional[str] = None) -> List[ReleaseRecord]:
        records = list(self._records.values())
        if kind is not None:
            records = [r for r in records if r.kind == kind]
        records.sort(key=lambda r: (r.kind, r.framework_version, r.version, r.registered_at))
        return records

    def resolve(
        self,
        kind: str,
        reporting_date: str,
        framework_version: str = "",
        require_approved: bool = True,
    ) -> ReleaseRecord:
        """Wählt deterministisch das passende Release für einen Stichtag.

        Reihenfolge: gültig + approved + spezifischste Framework-Version,
        bei Gleichstand neueste Registrierung. Fehlt ein Treffer, wird
        ``LookupError`` geworfen — die Engine muss das aktiv abfangen.
        """
        if kind not in VALID_KINDS:
            raise ValueError(f"unsupported release kind '{kind}'")
        candidates: List[ReleaseRecord] = []
        for record in self._records.values():
            if record.kind != kind:
                continue
            if not record.is_active():
                continue
            if require_approved and record.status != ReleaseStatus.APPROVED:
                continue
            if framework_version and record.framework_version not in ("", framework_version):
                continue
            if not record.covers(reporting_date):
                continue
            candidates.append(record)

        if not candidates:
            raise LookupError(
                f"no {'approved ' if require_approved else ''}release for kind={kind} "
                f"date={reporting_date} framework={framework_version or 'any'}"
            )

        candidates.sort(
            key=lambda r: (
                0 if r.framework_version == framework_version else 1,
                _date_key(r.valid_from),
                r.registered_at,
            ),
            reverse=True,
        )
        return candidates[0]

    def _must_get(self, release_id: str) -> ReleaseRecord:
        record = self._records.get(release_id)
        if record is None:
            raise KeyError(f"unknown release '{release_id}'")
        return record


def _date_key(value: str) -> str:
    return value or "0000-00-00"


def _intervals_overlap(a: ReleaseRecord, b: ReleaseRecord) -> bool:
    a_start = _parse_date(a.valid_from) or date.min
    a_end = _parse_date(a.valid_to) or date.max
    b_start = _parse_date(b.valid_from) or date.min
    b_end = _parse_date(b.valid_to) or date.max
    return a_start <= b_end and b_start <= a_end
