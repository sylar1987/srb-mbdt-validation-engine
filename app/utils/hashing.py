"""Stabile SHA-256-Hashes für Dateien, Verzeichnisse und Objekte (Phase 4).

Zentralisiert die Hash-Berechnung, die bisher an mehreren Stellen lose
implementiert war (Approval-Workflow, RunRecord.input_hash,
Metadata-Versioning). Ziel: deterministische, plattformneutrale Werte,
damit content_hash/input_hash über Prozesse hinweg vergleichbar bleiben.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Union


_CHUNK_SIZE = 64 * 1024


def hash_bytes(payload: bytes) -> str:
    """SHA-256-Hex über Bytes."""
    return hashlib.sha256(payload).hexdigest()


def hash_text(payload: str, encoding: str = "utf-8") -> str:
    """SHA-256-Hex über Text in UTF-8."""
    return hash_bytes(payload.encode(encoding))


def hash_file(path: Union[str, Path]) -> str:
    """SHA-256-Hex über den Inhalt einer Datei."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"hash target missing: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"hash target is not a file: {file_path}")
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def hash_object(obj: Any) -> str:
    """SHA-256-Hex über ein JSON-serialisierbares Objekt.

    Verwendet ``sort_keys=True`` und kompaktes Trennzeichen, damit das
    Resultat unabhängig von Dict-Einfügereihenfolge oder Whitespace ist.
    Nicht-JSON-serialisierbare Werte führen zu ``TypeError``.
    """
    try:
        canonical = json.dumps(
            obj,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        )
    except TypeError as exc:
        raise TypeError(f"object is not JSON-serialisable for hashing: {exc}") from exc
    return hash_text(canonical)


def hash_directory(
    path: Union[str, Path],
    pattern: str = "**/*",
    include_names: bool = True,
) -> str:
    """SHA-256-Hex über alle Dateien in ``path`` (rekursiv).

    Reihenfolge: lexikalisch sortiert nach POSIX-Relativpfad — damit ist
    der Hash plattformunabhängig stabil. ``include_names=True`` mixt den
    Dateinamen mit, sodass Umbenennungen den Hash ändern. Dateien werden
    chunked gelesen.
    """
    dir_path = Path(path)
    if not dir_path.exists():
        raise FileNotFoundError(f"hash directory missing: {dir_path}")
    if not dir_path.is_dir():
        raise ValueError(f"hash target is not a directory: {dir_path}")

    files = sorted(
        (p for p in dir_path.glob(pattern) if p.is_file()),
        key=lambda p: p.relative_to(dir_path).as_posix(),
    )
    digest = hashlib.sha256()
    for file_path in files:
        rel = file_path.relative_to(dir_path).as_posix()
        if include_names:
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
        with file_path.open("rb") as fh:
            while True:
                chunk = fh.read(_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        digest.update(b"\n")
    return digest.hexdigest()


def hash_iterable(items: Iterable[Any]) -> str:
    """SHA-256-Hex über eine Liste serialisierbarer Items (Reihenfolge bleibt!).

    Anders als ``hash_object`` mit Set wird die Iterationsreihenfolge
    explizit beibehalten — nützlich für Hash-Ketten, in denen die
    Reihenfolge bedeutsam ist (z. B. ein Lauf-Pfad).
    """
    return hash_object(list(items))


def _json_default(value: Any) -> Any:
    """Fallback für ``json.dumps``: Sets/Tuples → sortierte Listen, Path → str."""
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=lambda x: json.dumps(x, sort_keys=True, default=str))
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"unsupported type for hashing: {type(value).__name__}")


__all__ = [
    "hash_bytes",
    "hash_text",
    "hash_file",
    "hash_object",
    "hash_directory",
    "hash_iterable",
]
