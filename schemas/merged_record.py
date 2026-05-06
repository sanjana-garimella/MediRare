from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .case_report import CaseReport
from .extracted_figure import ExtractedFigure


class MergedRecord(BaseModel):
    pubmed_id: str
    disease: str
    case_report: Optional[CaseReport] = None
    figures: List[ExtractedFigure] = []
    merged_at: datetime

