"""Template-Lookup-Hilfen (inkl. TypeA/TypeB-Varianten)."""

from __future__ import annotations

from typing import List, Optional

import pandas as pd


def find_matching_keys(templates: dict, template_id: str) -> List[str]:
    return [k for k in templates if k == template_id or k.startswith(template_id)]


def get_template_df(templates: dict, template_id: str) -> Optional[pd.DataFrame]:
    if template_id in templates:
        return templates[template_id]
    for key in templates:
        if key.startswith(template_id):
            return templates[key]
    return None
