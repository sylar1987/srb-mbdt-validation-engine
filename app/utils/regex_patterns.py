"""Kompilierte Regex-Muster, identisch zur Legacy-Engine."""

from __future__ import annotations

import re

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(\s\d{2}:\d{2}:\d{2})?$")
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
LEI_RE = re.compile(r"^[0-9A-Z]{20}$")
ISO_3166_2_RE = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}$")

FIELD_CODE_4DIGIT = re.compile(r"^\d{4}$")
FIELD_CODE_C_PREFIX = re.compile(r"^c\d{4}$")
FIELD_CODE_SHORT_DIGIT = re.compile(r"^\d{1,3}$")
TEMPLATE_FILE_PREFIX = re.compile(r"(B\d{2}\.\d{2})")
