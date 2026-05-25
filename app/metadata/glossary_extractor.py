"""Extrahiert das Glossar als ``Dict[str, str]``."""

from __future__ import annotations

from typing import Dict

from app.metadata.package_reader import RawPackage


class GlossaryExtractor:
    def extract(self, raw: RawPackage) -> Dict[str, str]:
        return dict(raw.glossary)
