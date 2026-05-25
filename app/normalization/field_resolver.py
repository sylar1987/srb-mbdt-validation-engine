"""DPM-Feldauflösung für Header-Varianten.

Das SRB MBDT erlaubt zwei verbreitete Header-Konventionen in CSV-/XLSX-Eingaben:

  (A) Nur technische DPM-Bezeichnung
      ``c0040``, ``0040``, ``40``

  (B) Technische DPM-Bezeichnung mit Caption/Langtext, z. B.
      ``c0040 - Type of the unique identifier``
      ``c0040 – Type of the unique identifier``
      ``c0040 — Type of the unique identifier``
      ``c0040: Type of the unique identifier``
      ``c0040 (Type of the unique identifier)``
      ``0040 - Type of the unique identifier``

Zusätzlich kommt es vor, dass Headerzeilen nur die Caption enthalten
(Variante C). In diesem Fall kann eindeutiges Caption-Mapping über
``field_structure.json`` rekonstruiert werden.

Dieses Modul kapselt:

* ``extract_field_code_from_header(name)`` – extrahiert den technischen
  Code aus einem kombinierten Header (Varianten A und B).
* ``FieldResolver`` – nutzt die ``FieldStructure``, um Caption-only
  Header eines Templates eindeutig auf technische Codes zu mappen.
* ``resolve_dataframe_columns(df, template_id, field_structure)`` –
  benennt DataFrame-Spalten so um, dass nachfolgende Validatoren
  ausschließlich technische Codes (``cNNNN``) sehen.

Es werden bewusst keine stillen Fehlmappings vorgenommen: uneindeutige
Captions bleiben unverändert; doppelte technische Codes werden mit
``_1``, ``_2`` … dedupliziert, damit die bestehende Pipeline weiter
funktioniert und der Quality-Check sie als Konflikt erkennen kann.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

# Mögliche Trenner zwischen Code und Caption.
# ``-`` ASCII-Bindestrich, ``–`` U+2013 EN DASH, ``—`` U+2014 EM DASH,
# ``:`` Doppelpunkt, ``|`` Pipe, ``/`` Slash. Klammern werden separat behandelt.
_SEPARATORS = r"[\-–—:|/]"

# 1) ``c0040 - Caption`` / ``c0040: Caption`` / ``c0040 — Caption``
_RE_C_PREFIX_WITH_CAPTION = re.compile(
    rf"^\s*(?P<code>c\d{{3,5}})\s*{_SEPARATORS}\s*(?P<caption>.+?)\s*$",
    re.IGNORECASE,
)
# 2) ``c0040 (Caption)``
_RE_C_PREFIX_PAREN = re.compile(
    r"^\s*(?P<code>c\d{3,5})\s*\((?P<caption>[^)]+)\)\s*$",
    re.IGNORECASE,
)
# 3) ``0040 - Caption``
_RE_DIGIT_WITH_CAPTION = re.compile(
    rf"^\s*(?P<digits>\d{{1,5}})\s*{_SEPARATORS}\s*(?P<caption>.+?)\s*$",
)
# 4) ``0040 (Caption)``
_RE_DIGIT_PAREN = re.compile(
    r"^\s*(?P<digits>\d{1,5})\s*\((?P<caption>[^)]+)\)\s*$",
)
# 5) Reines ``c0040`` / ``0040`` / ``40``
_RE_C_ONLY = re.compile(r"^\s*(?P<code>c\d{3,5})\s*$", re.IGNORECASE)
_RE_DIGIT_ONLY = re.compile(r"^\s*(?P<digits>\d{1,5})\s*$")


def _canonical_code(raw_code: str) -> str:
    """Normalisiert einen rohen Code zu ``cNNNN`` (mindestens 4-stellig)."""
    s = raw_code.strip().lower()
    if s.startswith("c"):
        s = s[1:]
    s = s.lstrip("0") or "0"
    # mindestens 4-stellig (z. B. 40 → 0040), höhere Stellen erhalten
    return "c" + s.zfill(4)


def extract_field_code_from_header(name: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrahiert ``(technischer Code, Caption)`` aus einem Header-String.

    Rückgabewerte:
        ``(code, caption)`` – ``code`` ist ``cNNNN`` oder ``None``,
        ``caption`` ist die optional gefundene Caption.

    Beispiele:
        ``"c0040"``                     → ``("c0040", None)``
        ``"c0040 - Type of ..."``       → ``("c0040", "Type of ...")``
        ``"c0040 – Type of ..."``       → ``("c0040", "Type of ...")``
        ``"0040 (Caption)"``           → ``("c0040", "Caption")``
        ``"Type of ..."``              → ``(None, "Type of ...")``
        ``"col_5"``                    → ``(None, None)``
    """
    if name is None:
        return None, None
    s = str(name).strip()
    if not s:
        return None, None

    m = _RE_C_PREFIX_PAREN.match(s)
    if m:
        return _canonical_code(m.group("code")), m.group("caption").strip()

    m = _RE_C_PREFIX_WITH_CAPTION.match(s)
    if m:
        return _canonical_code(m.group("code")), m.group("caption").strip()

    m = _RE_DIGIT_PAREN.match(s)
    if m:
        return _canonical_code(m.group("digits")), m.group("caption").strip()

    m = _RE_DIGIT_WITH_CAPTION.match(s)
    if m:
        return _canonical_code(m.group("digits")), m.group("caption").strip()

    m = _RE_C_ONLY.match(s)
    if m:
        return _canonical_code(m.group("code")), None

    m = _RE_DIGIT_ONLY.match(s)
    if m:
        return _canonical_code(m.group("digits")), None

    # Reine Caption → kein Code extrahierbar.
    return None, s


def _normalize_caption(label: str) -> str:
    """Vergleichsnormalisierung für Captions (case-/whitespace-insensitiv)."""
    return re.sub(r"\s+", " ", str(label or "").strip().lower())


class FieldResolver:
    """Mappt Header-Strings eines Templates auf technische DPM-Codes.

    Funktionsweise:

    * Wird mit der ``FieldStructure`` und der Template-ID konstruiert.
    * Baut ein Caption→Code-Mapping aus ``field_structure.json``.
    * Captions, die im Template mehrfach vorkommen, gelten als
      uneindeutig (``ambiguous``) – sie werden nicht stillschweigend
      gemappt, sondern in ``ambiguous_captions`` dokumentiert.
    """

    def __init__(
        self,
        template_id: str,
        field_structure: Optional[Any] = None,
        *,
        field_label_pairs: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        self.template_id = template_id
        self._caption_to_code: Dict[str, str] = {}
        self._ambiguous_captions: set[str] = set()
        self._known_codes: set[str] = set()

        pairs: List[Tuple[str, str]] = []
        if field_label_pairs is not None:
            pairs = list(field_label_pairs)
        elif field_structure is not None:
            pairs = self._extract_pairs_from_field_structure(template_id, field_structure)

        seen_by_caption: Dict[str, str] = {}
        for code, label in pairs:
            if not code:
                continue
            self._known_codes.add(code.lower())
            norm = _normalize_caption(label)
            if not norm:
                continue
            if norm in seen_by_caption and seen_by_caption[norm].lower() != code.lower():
                self._ambiguous_captions.add(norm)
                self._caption_to_code.pop(norm, None)
            else:
                seen_by_caption.setdefault(norm, code)
                if norm not in self._ambiguous_captions:
                    self._caption_to_code[norm] = code

    @staticmethod
    def _extract_pairs_from_field_structure(
        template_id: str, field_structure: Any
    ) -> List[Tuple[str, str]]:
        """Liefert ``[(code, label), …]`` für ein Template.

        Unterstützt drei Eingaben:
          * ``FieldStructure``-Modell (``app.models.field_structure``)
          * Rohes ``dict`` aus ``field_structure.json`` (beide Schemavarianten)
          * Liste von Field-Dicts (bereits Template-spezifisch)
        """
        if field_structure is None:
            return []

        # Modell mit .get(template_id) → TemplateStructure
        if hasattr(field_structure, "get") and not isinstance(field_structure, dict):
            tpl = field_structure.get(template_id)
            if tpl is None and "_" in template_id:
                tpl = field_structure.get(template_id.split("_", 1)[0])
            if tpl is None:
                return []
            return [
                (str(getattr(f, "field_code", "")), str(getattr(f, "label", "")))
                for f in getattr(tpl, "fields", [])
            ]

        # Rohes dict aus field_structure.json
        if isinstance(field_structure, Mapping):
            entries = field_structure.get(template_id)
            if entries is None and "_" in template_id:
                entries = field_structure.get(template_id.split("_", 1)[0])
            entries = entries or []
            return [
                (
                    str(e.get("field_code") or e.get("code") or ""),
                    str(e.get("label") or ""),
                )
                for e in entries
            ]

        # Liste von Field-Dicts
        if isinstance(field_structure, list):
            return [
                (
                    str(e.get("field_code") or e.get("code") or ""),
                    str(e.get("label") or ""),
                )
                for e in field_structure
            ]
        return []

    def resolve_header(self, header: str) -> Tuple[Optional[str], str]:
        """Mappt einen Header auf einen technischen Code.

        Rückgabe:
            ``(code_or_none, reason)`` mit reason in
            ``{"code", "code+caption", "caption", "caption_ambiguous", "unknown"}``.
        """
        code, caption = extract_field_code_from_header(header)
        if code is not None:
            return code, ("code+caption" if caption else "code")

        if caption is None:
            return None, "unknown"

        norm = _normalize_caption(caption)
        if norm in self._ambiguous_captions:
            return None, "caption_ambiguous"
        mapped = self._caption_to_code.get(norm)
        if mapped:
            return mapped, "caption"
        return None, "unknown"

    @property
    def known_codes(self) -> set[str]:
        return set(self._known_codes)

    @property
    def ambiguous_captions(self) -> set[str]:
        return set(self._ambiguous_captions)


def resolve_dataframe_columns(
    df,
    template_id: str,
    field_structure: Optional[Any] = None,
) -> Tuple[Any, List[Dict[str, str]]]:
    """Benennt Spalten in ``df`` auf technische DPM-Codes um.

    Strategie:
      1. Erst direkter Code-Match (Varianten A/B).
      2. Wenn nicht möglich und ``field_structure`` vorhanden ist,
         Caption-Mapping nutzen (Variante C, nur bei eindeutiger
         Zuordnung).
      3. Sonst Spaltenname unverändert lassen.

    Doppelte Zielspalten werden mit ``_1``, ``_2`` … dedupliziert.

    Rückgabe:
        ``(df_renamed, diagnostics)`` – ``diagnostics`` ist eine Liste
        kleiner dict-Einträge mit ``original``, ``resolved``, ``reason``.
    """
    if df is None:
        return df, []

    resolver = FieldResolver(template_id, field_structure)

    new_cols: List[str] = []
    seen: Dict[str, int] = {}
    diagnostics: List[Dict[str, str]] = []

    for original in list(df.columns):
        orig_str = str(original)
        code, reason = resolver.resolve_header(orig_str)
        if code is None:
            target = orig_str
        else:
            target = code

        if target in seen:
            seen[target] += 1
            target = f"{target}_{seen[target]}"
        else:
            seen[target] = 0

        new_cols.append(target)
        diagnostics.append({"original": orig_str, "resolved": target, "reason": reason})

    df = df.copy()
    df.columns = new_cols
    return df, diagnostics
