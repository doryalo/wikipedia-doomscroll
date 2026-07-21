import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .db import get_connection
from .enrichment import ArticleDossier, DiscoverySynthesis, TagKind
from .enrichment_repository import (
    get_enrichment,
    get_post_enrichment,
    list_enrichments,
    list_enrichments_by_tag,
    list_tags,
)

router = APIRouter()
Connection = Annotated[sqlite3.Connection, Depends(get_connection)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


class StoredTag(BaseModel):
    kind: TagKind
    slug: str
    label: str
    taxonomy_path: list[str]
    rank: int
    confidence: float
    rationale: str
    evidence_ids: list[str]


class EnrichmentResponse(BaseModel):
    article_id: str
    title: str
    url: str | None
    language: str
    enrichment_run_id: int
    schema_version: int
    prompt_version: str
    extraction_model: str
    synthesis_model: str
    completed_at: str
    extraction: ArticleDossier
    synthesis: DiscoverySynthesis
    tags: list[StoredTag]


class TagSummary(BaseModel):
    kind: TagKind
    slug: str
    label: str
    taxonomy_path: list[str]
    article_count: int


class PostEnrichmentResponse(BaseModel):
    post_id: str
    post_title: str
    post_content: str
    enrichment: EnrichmentResponse


@router.get("/enrichments", response_model=list[EnrichmentResponse], tags=["enrichment"])
def all_enrichments(
    connection: Connection, limit: PageSize = 50, offset: Offset = 0
) -> list[dict[str, object]]:
    return list_enrichments(connection, limit=limit, offset=offset)


@router.get(
    "/enrichments/{article_id}",
    response_model=EnrichmentResponse,
    tags=["enrichment"],
)
def enrichment_by_article(
    article_id: str, connection: Connection
) -> dict[str, object]:
    enrichment = get_enrichment(connection, article_id)
    if enrichment is None:
        raise HTTPException(status_code=404, detail="enrichment not found")
    return enrichment


@router.get("/tags", response_model=list[TagSummary], tags=["enrichment"])
def all_tags(
    connection: Connection, limit: PageSize = 100, offset: Offset = 0
) -> list[dict[str, object]]:
    return list_tags(connection, limit=limit, offset=offset)


@router.get(
    "/tags/{kind}/{slug}/enrichments",
    response_model=list[EnrichmentResponse],
    tags=["enrichment"],
)
def enrichments_by_tag(
    kind: TagKind,
    slug: str,
    connection: Connection,
    limit: PageSize = 50,
    offset: Offset = 0,
) -> list[dict[str, object]]:
    return list_enrichments_by_tag(
        connection, kind=kind, slug=slug, limit=limit, offset=offset
    )


@router.get(
    "/posts/{post_id}/enrichment",
    response_model=PostEnrichmentResponse,
    tags=["enrichment"],
)
def enrichment_by_post(post_id: str, connection: Connection) -> dict[str, object]:
    enrichment = get_post_enrichment(connection, post_id)
    if enrichment is None:
        raise HTTPException(status_code=404, detail="post enrichment not found")
    return enrichment
