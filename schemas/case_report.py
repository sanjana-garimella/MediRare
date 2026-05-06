from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class CaseReport(BaseModel):
    pubmed_id: str = Field(..., description="PubMed article ID as a string")
    disease: str = Field(..., description="SLE | Sjogrens | MCTD")
    title: str
    abstract: str
    misdiagnosis_sequence: List[str] = Field(default_factory=list)
    extracted_at: datetime

