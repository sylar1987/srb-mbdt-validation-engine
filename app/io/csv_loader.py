"""CSV-Eingaben laden (Verzeichnis oder Einzeldatei)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from app.models import InputBatch, TemplateData
from app.normalization.field_resolver import resolve_dataframe_columns
from app.normalization.headers import normalize_col_names
from app.normalization.missing import replace_blank_with_na
from app.utils.regex_patterns import TEMPLATE_FILE_PREFIX


def _read_csv(filepath: Path) -> pd.DataFrame:
    df = pd.read_csv(
        filepath, sep=";", dtype=str,
        encoding="utf-8-sig", keep_default_na=False,
    )
    df.columns = normalize_col_names(df.columns.tolist())
    return replace_blank_with_na(df)


def _apply_caption_resolution(
    df: pd.DataFrame, template_id: str, field_structure: Any
) -> pd.DataFrame:
    if field_structure is None:
        return df
    df_resolved, _diag = resolve_dataframe_columns(df, template_id, field_structure)
    return df_resolved


def load_csv_dir(
    directory: str | Path,
    batch: Optional[InputBatch] = None,
    field_structure: Any = None,
) -> InputBatch:
    """Lädt alle ``B##.##*.csv``-Dateien aus einem Verzeichnis."""
    batch = batch or InputBatch(source_type="csv_dir", source_path=str(directory))
    dirp = Path(directory)
    for csv_file in dirp.glob("*.csv"):
        m = TEMPLATE_FILE_PREFIX.match(csv_file.stem)
        if not m:
            continue
        tpl_id = m.group(1)
        suffix = csv_file.stem.replace(tpl_id, "").strip("_")
        key = f"{tpl_id}_{suffix}" if suffix else tpl_id
        try:
            df = _read_csv(csv_file)
        except Exception as exc:
            print(f"  WARNUNG: CSV '{csv_file.name}' konnte nicht gelesen werden: {exc}")
            continue
        df = _apply_caption_resolution(df, tpl_id, field_structure)
        if key in batch.templates:
            df = pd.concat([batch.templates[key], df], ignore_index=True)
            batch.template_objects[key].df = df
            batch.templates[key] = df
        else:
            batch.add(TemplateData(
                template_id=tpl_id,
                key=key,
                df=df,
                variant=suffix or None,
                source_name=csv_file.name,
            ))
    return batch


def load_single_csv(
    filepath: str | Path,
    template_id: str,
    batch: Optional[InputBatch] = None,
    field_structure: Any = None,
) -> InputBatch:
    """Lädt eine einzelne CSV-Datei als spezifisches Template."""
    batch = batch or InputBatch(source_type="csv_file", source_path=str(filepath))
    df = _read_csv(Path(filepath))
    df = _apply_caption_resolution(df, template_id, field_structure)
    batch.add(TemplateData(
        template_id=template_id,
        key=template_id,
        df=df,
        variant=None,
        source_name=Path(filepath).name,
    ))
    return batch
