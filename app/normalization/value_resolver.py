"""DPM Value-Alias-Auflösung.

Akzeptiert zwei Eingabe-Varianten gegen eine zulässige Codelist:

A) Technischer Code allein, z.B. ``SCT``.
B) ``CODE`` + Caption, z.B.
   - ``SCT - Secured collateralized liabilities``
   - ``SCT: Secured...``
   - ``SCT (Secured...)``
   - ``SCT | Secured...``

Technischer Code hat Vorrang. ``CODE + Caption`` wird auf ``CODE`` reduziert,
sofern ``CODE`` in der erlaubten Werteliste ist. Caption-only wird nur dann
auf einen Code gemappt, wenn die Caption eindeutig ist und ein optionales
Mapping ``caption -> code`` vorliegt.

Numerische Werte, Datumswerte und LEIs werden nicht angefasst: Der Splitter
arbeitet ausschließlich, wenn das Trennzeichen vorhanden ist UND der
linke Token bereits als zulässiger Code erkannt wird.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

# Reihenfolge ist wichtig: ``-`` zuletzt, da LEI etc. Bindestrich enthalten
# darf. Wir prüfen jedes Separator-Pattern und nehmen den ersten Treffer.
_SEPARATORS = (
    re.compile(r"\s*\|\s*"),
    re.compile(r"\s*:\s*"),
    re.compile(r"\s*\(\s*"),
    re.compile(r"\s+-\s+"),
)


@dataclass(frozen=True)
class ResolutionResult:
    """Ergebnis einer Wert-Auflösung.

    Attribute:
      value: aufgelöster technischer Wert (oder Original, falls keine
        Auflösung möglich).
      matched: ``True``, wenn der Eingabewert eindeutig einem erlaubten
        Wert zugeordnet werden konnte.
      ambiguous: ``True``, wenn Caption-only mehrdeutig war.
      reason: Diagnosehinweis (kurz, deutsch).
    """

    value: str
    matched: bool
    ambiguous: bool = False
    reason: str = ""


def _split_code_caption(text: str) -> Optional[str]:
    """Trennt ``CODE`` von Caption per bekannter Separatoren.

    Gibt den linken Token zurück oder ``None``, wenn kein Separator passt.
    """
    for sep in _SEPARATORS:
        m = sep.search(text)
        if m and m.start() > 0:
            return text[: m.start()].strip()
    return None


def _build_caption_index(
    allowed: Sequence[str],
    caption_map: Optional[Mapping[str, str]] = None,
) -> Mapping[str, list]:
    """Erzeugt einen Index ``caption_lower -> [codes]``.

    Quelle: optionales explizites ``caption_map`` ({caption: code}).
    """
    index: dict[str, list] = {}
    if caption_map:
        for caption, code in caption_map.items():
            key = caption.strip().lower()
            if not key:
                continue
            index.setdefault(key, []).append(code)
    return index


def resolve_value(
    raw: str,
    allowed: Iterable[str],
    caption_map: Optional[Mapping[str, str]] = None,
) -> ResolutionResult:
    """Versucht ``raw`` gegen ``allowed`` aufzulösen.

    - Exakter Codetreffer => ``matched=True``, ``value=raw_stripped``.
    - ``CODE + Caption`` mit erlaubtem CODE => reduziert auf CODE.
    - Caption-only mit eindeutigem Mapping => Code.
    - Caption-only ambig => ``ambiguous=True``, ``matched=False``.
    - Sonst: ``matched=False``, Original zurück.
    """
    if raw is None:
        return ResolutionResult(value="", matched=False, reason="leer")

    s = str(raw).strip()
    if not s:
        return ResolutionResult(value="", matched=False, reason="leer")

    allowed_list = [str(v).strip() for v in allowed]
    allowed_set = {v for v in allowed_list if v}

    # Variante A: exakter Code
    if s in allowed_set:
        return ResolutionResult(value=s, matched=True)

    # Variante B: CODE + Caption – linker Token als erlaubter Code?
    left = _split_code_caption(s)
    if left and left in allowed_set:
        return ResolutionResult(
            value=left,
            matched=True,
            reason="aus 'CODE + Caption' reduziert",
        )

    # Caption-only über explizites Mapping
    caption_index = _build_caption_index(allowed_list, caption_map)
    if caption_index:
        key = s.lower()
        # auch geklammerte/abgeschnittene Caption normalisieren
        key = key.rstrip(" )").strip()
        hits = caption_index.get(key, [])
        if len(hits) == 1 and hits[0] in allowed_set:
            return ResolutionResult(
                value=hits[0],
                matched=True,
                reason="Caption eindeutig gemappt",
            )
        if len(hits) > 1:
            return ResolutionResult(
                value=s,
                matched=False,
                ambiguous=True,
                reason="Caption mehrdeutig",
            )

    return ResolutionResult(
        value=s,
        matched=False,
        reason="kein Treffer in Codeliste",
    )


def canonicalize_for_compare(raw: str, allowed: Optional[Iterable[str]] = None) -> str:
    """Reduziert ``CODE + Caption`` auf ``CODE`` für sichere Stringvergleiche.

    - Mit ``allowed``: nur reduzieren, wenn linker Token in ``allowed``.
    - Ohne ``allowed``: nur reduzieren, wenn linker Token wie ein Code
      aussieht (kurz, keine Whitespaces, alphanumerisch/Unterstrich).
      Numerische Werte, Datumswerte (mit ``-``), LEI (20 Zeichen) und
      Werte ohne bekannten Separator bleiben unverändert.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return s

    if allowed is not None:
        allowed_set = {str(v).strip() for v in allowed}
        left = _split_code_caption(s)
        if left and left in allowed_set:
            return left
        return s

    # Heuristik ohne Codeliste:
    left = _split_code_caption(s)
    if not left:
        return s
    # Reine Zahl (z.B. "2024-12-31" -> erste Hälfte "2024" => Datum schützen)
    if left.isdigit():
        return s
    # LEI sind 20 Zeichen alphanumerisch – zu lang für typischen Code
    if len(left) >= 18 and left.isalnum():
        return s
    # akzeptiere kurze Codes: Buchstaben/Ziffern/_/. ohne Whitespace
    if re.fullmatch(r"[A-Za-z0-9_.]{1,16}", left):
        return left
    return s
