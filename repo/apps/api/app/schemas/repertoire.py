from __future__ import annotations

from pydantic import BaseModel


class RepertoireItemCardResponse(BaseModel):
    id: str
    title: str
    composer: str | None
    tags: list[str]
    performer_names: list[str]
    regions: list[str]


class RepertoireItemDetailResponse(RepertoireItemCardResponse):
    performer_count: int


class RepertoireSearchResponse(BaseModel):
    results: list[RepertoireItemCardResponse]
    total: int
