"""Smoke-Test: alle neuen Module sind importierbar."""

from __future__ import annotations


def test_imports():
    import app  # noqa: F401
    from app.models import (  # noqa: F401
        InputBatch,
        TemplateData,
        RuleDefinition,
        ValidationIssue,
        ValidationSummary,
    )
    from app.config import load_catalog, load_field_structure  # noqa: F401
    from app.io import load_csv_dir, load_xlsx, load_single_csv  # noqa: F401
    from app.normalization import (  # noqa: F401
        normalize_col_names,
        find_header_row,
        extract_headers,
    )
    from app.utils import is_missing, safe_float, parse_date  # noqa: F401
    from app.services import extract_reference_date  # noqa: F401
    from app.validation import ValidationContext, Dispatcher, ValidationEngine  # noqa: F401
    from app.reporting import build_summary, write_excel_report  # noqa: F401
    from app.runner import Runner  # noqa: F401
    from app.settings import EngineSettings  # noqa: F401
