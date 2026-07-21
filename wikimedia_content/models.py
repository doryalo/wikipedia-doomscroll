"""Pydantic v2 representations for the Wikimedia example datasets.

Load a single dataset with ``load_dataset(path)`` or every dataset in this
folder with ``load_all_datasets()``.  The models intentionally expose text
content and page-card metadata only; image fields are not part of the contract.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects fields outside the published JSON schema."""

    model_config = ConfigDict(extra="forbid")


class Source(StrictModel):
    endpoint: str
    parameters: dict[str, Any]


class Expansion(StrictModel):
    mode: Literal["natural", "expanded"]
    anchor: str | None
    shortfall: bool
    note: str | None


class PageIdentity(StrictModel):
    wiki: str = Field(min_length=1)
    page_id: int = Field(ge=1)
    title: str = Field(min_length=1)
    canonical_url: str
    revision_id: int = Field(ge=1)
    revision_timestamp: datetime


class PageCard(StrictModel):
    description: str | None
    wikidata_id: str | None
    length_bytes: int = Field(ge=0)
    last_touched: datetime
    is_disambiguation: bool


class PageContent(StrictModel):
    full_plain_text: str = Field(min_length=1)


class PageResult(StrictModel):
    rank: int = Field(ge=1, le=10)
    discovery: dict[str, Any]
    identity: PageIdentity
    card: PageCard
    content: PageContent


class PageResultsDataset(StrictModel):
    """One generated discovery dataset, mirroring ``page-results.schema.json``."""

    schema_version: Literal["1.0.0"]
    example_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    retrieved_at: datetime
    wiki: str = Field(min_length=1)
    source: Source
    expansion: Expansion
    result_count: int = Field(ge=0, le=10)
    pages: list[PageResult] = Field(max_length=10)

    @model_validator(mode="after")
    def validate_page_collection(self) -> "PageResultsDataset":
        """Enforce envelope relationships expressed by the JSON schema."""

        if self.result_count != len(self.pages):
            raise ValueError("result_count must equal the number of pages")
        if not self.expansion.shortfall and self.result_count != 10:
            raise ValueError("non-shortfall datasets must contain exactly 10 pages")

        ranks = [page.rank for page in self.pages]
        if ranks != list(range(1, self.result_count + 1)):
            raise ValueError("page ranks must be sequential, starting at 1")

        page_ids = [page.identity.page_id for page in self.pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("page identities must be unique within a dataset")
        return self


Dataset = PageResultsDataset
"""Short alias for the root page-results dataset model."""


def load_dataset(path: str | Path) -> PageResultsDataset:
    """Read and validate one dataset JSON file."""

    dataset_path = Path(path)
    return PageResultsDataset.model_validate_json(dataset_path.read_text(encoding="utf-8"))


def load_all_datasets(directory: str | Path | None = None) -> dict[str, PageResultsDataset]:
    """Read every generated dataset in *directory*, excluding the JSON schema."""

    dataset_directory = Path(directory) if directory is not None else Path(__file__).parent
    datasets: dict[str, PageResultsDataset] = {}
    for path in sorted(dataset_directory.glob("*.json")):
        if path.name == "page-results.schema.json":
            continue
        datasets[path.stem] = load_dataset(path)
    return datasets

