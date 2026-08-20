from __future__ import annotations
from pydantic import BaseModel, Field

class AnalyzeRequest(BaseModel):
    prompt: str = Field(min_length=20, max_length=2_000_000)
    knowledge_limit: int = Field(default=8, ge=0, le=20)

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=30)

class ReportRequest(BaseModel):
    prompt: str = Field(min_length=20, max_length=2_000_000)
    analysis: dict | None = None
