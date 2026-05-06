from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ExtractedFigure(BaseModel):
    pubmed_id: str
    disease: str = Field(default="", description="Optional in Week 1 if unknown")
    figure_index: int
    figure_type: str = Field(default="other")
    file_path: str
    caption: str = Field(default="")
    clinical_relevance: str = Field(default="unknown")
    extracted_at: datetime
    source_pdf: str = Field(default="", description="Where the image came from")

