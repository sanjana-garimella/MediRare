from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CaseReport(BaseModel):
    pubmed_id: str = Field(..., description="PubMed article ID as a string")
    disease: str = Field(..., description="SLE | Sjogrens | MCTD")
    title: str
    abstract: str
    misdiagnosis_sequence: List[str] = Field(default_factory=list)
    misdiagnosis_provenance: Optional[str] = Field(
        default=None,
        description=(
            "high | medium | gazetteer | llm | reviewed | legacy_unreviewed | "
            "signal_only | none"
        ),
    )
    misdiagnosis_extracted_at: Optional[datetime] = None
    extracted_at: datetime

