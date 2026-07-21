"""Live FastAPI adapter for the Wikimedia examples.

Run with an environment that provides ``fastapi`` and ``httpx``:

    WIKIMEDIA_CONTACT='you@example.org' uvicorn wikimedia_api.main:app --reload
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
import os
from pathlib import Path
import re
import tempfile
from typing import Any, AsyncIterator, Literal
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, BadRequestError, RateLimitError
from pydantic import BaseModel, Field, field_validator

from wikimedia_content.models import PageResultsDataset


LANGUAGE = os.getenv("WIKIMEDIA_LANGUAGE", "en")
CONTACT = os.getenv("WIKIMEDIA_CONTACT", "replace-with-monitored-contact@example.org")
ACTION_API = f"https://{LANGUAGE}.wikipedia.org/w/api.php"
CORE_REST = f"https://{LANGUAGE}.wikipedia.org/w/rest.php/v1"
ANALYTICS = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top"
FEED = f"https://{LANGUAGE}.wikipedia.org/api/rest_v1/feed"
MAX_PAGES = 10
RAW_ARTICLE_DIR = Path(__file__).resolve().parents[1] / "backend" / "data" / "raw-articles"
RAW_IMAGE_DIR = Path(__file__).resolve().parents[1] / "backend" / "data" / "raw-images"
POST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class StoredResponse(BaseModel):
    status: Literal["stored"] = "stored"


class MediaGenerationRequest(BaseModel):
    post_id: str = Field(alias="postId", min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=4_000)
    logical_value: str = Field(alias="logicalValue", min_length=1, max_length=2_000)
    time_frame: str = Field(alias="timeFrame", min_length=1, max_length=500)
    concept: str = Field(min_length=1, max_length=2_000)
    intent: str = Field(min_length=1, max_length=2_000)

    @field_validator("post_id")
    @classmethod
    def require_safe_post_id(cls, value: str) -> str:
        if not POST_ID_PATTERN.fullmatch(value):
            raise ValueError("postId must be filesystem-safe")
        return value


@dataclass(frozen=True)
class MediaRecord:
    artifact_path: Path
    sidecar_path: Path


class ImageGenerationResponse(BaseModel):
    media_id: str = Field(alias="mediaId")
    post_id: str = Field(alias="postId")
    kind: Literal["image"]
    status: Literal["completed"]
    model: str
    artifact_url: str = Field(alias="artifactUrl")


class ReelGenerationResponse(BaseModel):
    media_id: str = Field(alias="mediaId")
    post_id: str = Field(alias="postId")
    kind: Literal["reel"]
    status: Literal["queued", "in_progress", "completed", "failed"]
    model: str
    provider_job_id: str = Field(alias="providerJobId")
    progress: int | None = None
    status_url: str = Field(alias="statusUrl")
    artifact_url: str = Field(alias="artifactUrl")


def compose_media_prompt(request: MediaGenerationRequest, *, medium: str) -> str:
    return "\n".join(
        (
            f"Create a {medium}.",
            f"Description: {request.description}",
            f"Logical value: {request.logical_value}",
            f"Time frame: {request.time_frame}",
            f"Concept: {request.concept}",
            f"Intent: {request.intent}",
        )
    )


def _atomic_write_bytes(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=destination.parent,
        prefix=f".{destination.stem}-",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
        try:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary_path, destination)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise


def write_media_record(
    *,
    directory: Path,
    post_id: str,
    media_id: str,
    kind: Literal["image", "reel"],
    extension: Literal["png", "mp4"],
    content: bytes | None,
    metadata: dict[str, Any],
) -> MediaRecord:
    """Atomically persist an ID-addressable artifact and its durable sidecar."""

    if not POST_ID_PATTERN.fullmatch(post_id):
        raise ValueError("post_id must be filesystem-safe")
    if not re.fullmatch(r"[a-f0-9]{32}", media_id):
        raise ValueError("media_id must be a UUID hex value")
    artifact_path = directory / f"{media_id}.{extension}"
    sidecar_path = directory / "debug" / f"{media_id}.json"
    payload = {
        **metadata,
        "media_id": media_id,
        "post_id": post_id,
        "kind": kind,
        "artifact_filename": artifact_path.name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if content is not None:
        _atomic_write_bytes(artifact_path, content)
    _atomic_write_bytes(
        sidecar_path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode(),
    )
    return MediaRecord(artifact_path=artifact_path, sidecar_path=sidecar_path)


class UpstreamError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message


class UpstreamCoordinator:
    """Shared 200 request/minute and three-concurrent-call upstream guard."""

    def __init__(self, per_minute: int = 200, concurrency: int = 3) -> None:
        self.per_minute = per_minute
        self.timestamps: deque[float] = deque()
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(concurrency)

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            async with self.lock:
                now = loop.time()
                while self.timestamps and now - self.timestamps[0] >= 60:
                    self.timestamps.popleft()
                if len(self.timestamps) < self.per_minute:
                    self.timestamps.append(now)
                    return
                wait_seconds = 60 - (now - self.timestamps[0])
            await asyncio.sleep(max(wait_seconds, 0.01))


def _action(**params: Any) -> dict[str, Any]:
    return {"action": "query", "format": "json", "formatversion": 2, **params}


def _safe_wikimedia_url(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    allowed = ("wikipedia.org", "wikimedia.org", "wikidata.org")
    if not any(host == suffix or host.endswith(f".{suffix}") for suffix in allowed):
        raise ValueError(f"non-Wikimedia host rejected: {host}")


def _pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get("query", {}).get("pages", [])


def _title(value: dict[str, Any]) -> str | None:
    return value.get("title") or value.get("titles", {}).get("normalized")


def round_robin_category_articles(
    members_by_category: dict[str, list[str]], count: int
) -> list[tuple[str, str]]:
    """Take one distinct article per category per pass, in discovery order."""

    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    offset = 0
    while len(result) < count:
        selected_this_round = False
        for category, titles in members_by_category.items():
            if offset >= len(titles):
                continue
            title = titles[offset]
            if title not in seen:
                seen.add(title)
                result.append((category, title))
                selected_this_round = True
                if len(result) == count:
                    return result
        if not selected_this_round and all(offset >= len(items) for items in members_by_category.values()):
            return result
        offset += 1
    return result


def write_raw_article(
    dataset: PageResultsDataset, directory: Path = RAW_ARTICLE_DIR
) -> Path:
    """Atomically publish one validated envelope for the backend watcher."""

    directory.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^a-z0-9-]+", "-", dataset.example_id.lower()).strip("-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = directory / f"{safe_id}-{timestamp}-{uuid4().hex}.json"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=directory, prefix=f".{safe_id}-", suffix=".tmp", delete=False
    ) as handle:
        temporary_path = Path(handle.name)
        try:
            handle.write(dataset.model_dump_json(indent=2))
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary_path, destination)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    return destination


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if CONTACT.startswith("replace-"):
        raise RuntimeError("Set WIKIMEDIA_CONTACT to a monitored email or HTTPS contact URL")
    app.state.coordinator = UpstreamCoordinator()
    app.state.client = httpx.AsyncClient(
        headers={
            "User-Agent": f"WikipediaDoomscrollAPI/0.1 (+{CONTACT})",
            "Accept-Encoding": "gzip",
        },
        timeout=httpx.Timeout(20.0, connect=5.0),
        follow_redirects=True,
    )
    if not hasattr(app.state, "media_dir"):
        app.state.media_dir = RAW_IMAGE_DIR
    openai_key = os.getenv("OPENAI_API_KEY")
    app.state.openai = AsyncOpenAI(api_key=openai_key) if openai_key else None
    try:
        yield
    finally:
        await app.state.client.aclose()
        if app.state.openai is not None:
            await app.state.openai.close()


app = FastAPI(title="Live Wikimedia examples", version="0.1.0", lifespan=lifespan)


def _media_metadata(
    request: MediaGenerationRequest,
    *,
    kind: Literal["image", "reel"],
    model: str,
    status: str,
    provider_job_id: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "model": model,
        "status": status,
        "provider_job_id": provider_job_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt_inputs": request.model_dump(by_alias=True),
    }


def _openai_client(request: Request) -> AsyncOpenAI:
    client = getattr(request.app.state, "openai", None)
    if client is None:
        raise HTTPException(status_code=503, detail="OpenAI media generation is not configured")
    return client


def _media_sidecar_by_provider_job(directory: Path, job_id: str) -> tuple[Path, dict[str, Any]] | None:
    for sidecar_path in (directory / "debug").glob("*.json"):
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get("provider_job_id") == job_id:
            return sidecar_path, payload
    return None


def _load_media_sidecar(directory: Path, media_id: str) -> tuple[Path, dict[str, Any]]:
    if not re.fullmatch(r"[a-f0-9]{32}", media_id):
        raise HTTPException(status_code=404, detail="Generated media was not found")
    sidecar_path = directory / "debug" / f"{media_id}.json"
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Generated media was not found") from exc
    if payload.get("media_id") != media_id:
        raise HTTPException(status_code=404, detail="Generated media was not found")
    return sidecar_path, payload


@app.post(
    "/v1/media/images/generations",
    response_model=ImageGenerationResponse,
    status_code=201,
    tags=["media"],
)
async def generate_image(
    request: Request, body: MediaGenerationRequest
) -> ImageGenerationResponse:
    client = _openai_client(request)
    try:
        response = await client.images.generate(
            model="gpt-image-2",
            prompt=compose_media_prompt(body, medium="still image"),
        )
        encoded_image = response.data[0].b64_json
        if not encoded_image:
            raise HTTPException(status_code=502, detail="OpenAI returned no image content")
        image_bytes = base64.b64decode(encoded_image, validate=True)
    except HTTPException:
        raise
    except BadRequestError as exc:
        if getattr(exc, "code", None) == "moderation_blocked":
            raise HTTPException(status_code=422, detail="Image generation was blocked by safety checks") from exc
        raise HTTPException(status_code=502, detail="OpenAI rejected the image request") from exc
    except RateLimitError as exc:
        raise HTTPException(status_code=503, detail="OpenAI image generation is rate limited") from exc
    except APIConnectionError as exc:
        raise HTTPException(status_code=503, detail="OpenAI image generation is unavailable") from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=502, detail="OpenAI image generation failed") from exc
    except (IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="OpenAI returned invalid image content") from exc

    media_id = uuid4().hex
    try:
        write_media_record(
            directory=request.app.state.media_dir,
            post_id=body.post_id,
            media_id=media_id,
            kind="image",
            extension="png",
            content=image_bytes,
            metadata=_media_metadata(
                body, kind="image", model="gpt-image-2", status="completed"
            ),
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the generated image") from exc
    return ImageGenerationResponse(
        mediaId=media_id,
        postId=body.post_id,
        kind="image",
        status="completed",
        model="gpt-image-2",
        artifactUrl=f"/v1/media/{media_id}",
    )


def _reel_response(payload: dict[str, Any]) -> ReelGenerationResponse:
    post_id = payload["post_id"]
    media_id = payload["media_id"]
    provider_job_id = payload["provider_job_id"]
    return ReelGenerationResponse(
        mediaId=media_id,
        postId=post_id,
        kind="reel",
        status=payload["status"],
        model=payload["model"],
        providerJobId=provider_job_id,
        progress=payload.get("progress"),
        statusUrl=f"/v1/media/reels/generations/{provider_job_id}",
        artifactUrl=f"/v1/media/{media_id}",
    )


@app.post(
    "/v1/media/reels/generations",
    response_model=ReelGenerationResponse,
    status_code=202,
    tags=["media"],
)
async def generate_reel(
    request: Request, body: MediaGenerationRequest
) -> ReelGenerationResponse:
    client = _openai_client(request)
    try:
        # Sora 2 and the Videos API are scheduled to shut down on 2026-09-24.
        video = await client.videos.create(
            model="sora-2",
            prompt=compose_media_prompt(body, medium="short vertical reel"),
            size="720x1280",
            seconds="8",
        )
    except RateLimitError as exc:
        raise HTTPException(status_code=503, detail="OpenAI reel generation is rate limited") from exc
    except APIConnectionError as exc:
        raise HTTPException(status_code=503, detail="OpenAI reel generation is unavailable") from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=502, detail="OpenAI reel generation failed") from exc

    media_id = uuid4().hex
    status = getattr(video, "status", "queued")
    if status not in {"queued", "in_progress", "completed", "failed"}:
        status = "queued"
    payload = _media_metadata(
        body,
        kind="reel",
        model=getattr(video, "model", "sora-2"),
        status=status,
        provider_job_id=video.id,
    )
    payload["progress"] = getattr(video, "progress", None)
    try:
        write_media_record(
            directory=request.app.state.media_dir,
            post_id=body.post_id,
            media_id=media_id,
            kind="reel",
            extension="mp4",
            content=None,
            metadata=payload,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the reel request") from exc
    return _reel_response({**payload, "media_id": media_id, "post_id": body.post_id})


@app.get(
    "/v1/media/reels/generations/{job_id}",
    response_model=ReelGenerationResponse,
    tags=["media"],
)
async def reel_status(request: Request, job_id: str) -> ReelGenerationResponse:
    found = _media_sidecar_by_provider_job(request.app.state.media_dir, job_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Generated reel was not found")
    _, stored = found
    client = _openai_client(request)
    try:
        video = await client.videos.retrieve(job_id)
    except APIConnectionError as exc:
        raise HTTPException(status_code=503, detail="OpenAI reel generation is unavailable") from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=502, detail="OpenAI reel status lookup failed") from exc

    status = getattr(video, "status", stored["status"])
    if status not in {"queued", "in_progress", "completed", "failed"}:
        status = "failed"
    updated = {
        **stored,
        "status": status,
        "model": getattr(video, "model", stored["model"]),
        "progress": getattr(video, "progress", stored.get("progress")),
    }
    content: bytes | None = None
    if status == "completed" and not (
        request.app.state.media_dir / stored["artifact_filename"]
    ).is_file():
        try:
            downloaded = await client.videos.download_content(job_id)
            content = downloaded.content if hasattr(downloaded, "content") else downloaded
            if not isinstance(content, bytes):
                raise TypeError("video content was not bytes")
        except APIConnectionError as exc:
            raise HTTPException(status_code=503, detail="OpenAI reel download is unavailable") from exc
        except APIStatusError as exc:
            raise HTTPException(status_code=502, detail="OpenAI reel download failed") from exc
        except TypeError as exc:
            raise HTTPException(status_code=502, detail="OpenAI returned invalid reel content") from exc
    try:
        write_media_record(
            directory=request.app.state.media_dir,
            post_id=stored["post_id"],
            media_id=stored["media_id"],
            kind="reel",
            extension="mp4",
            content=content,
            metadata=updated,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the generated reel") from exc
    return _reel_response(updated)


@app.get("/v1/media/{media_id}", tags=["media"])
async def media_artifact(request: Request, media_id: str) -> FileResponse:
    if not re.fullmatch(r"[a-f0-9]{32}", media_id):
        raise HTTPException(status_code=404, detail="Generated media was not found")
    for extension, media_type in (("png", "image/png"), ("mp4", "video/mp4")):
        artifact_path = request.app.state.media_dir / f"{media_id}.{extension}"
        if artifact_path.is_file():
            return FileResponse(artifact_path, media_type=media_type, filename=artifact_path.name)
    try:
        _, stored = _load_media_sidecar(request.app.state.media_dir, media_id)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Generated media artifact was not found") from None
    if stored.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Generated media is not ready")
    raise HTTPException(status_code=404, detail="Generated media artifact was not found")


async def upstream_json(request: Request, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    _safe_wikimedia_url(url)
    query = dict(params or {})
    if url == ACTION_API:
        query.setdefault("maxlag", 5)
    coordinator: UpstreamCoordinator = request.app.state.coordinator
    await coordinator.acquire()
    async with coordinator.semaphore:
        try:
            response = await request.app.state.client.get(url, params=query)
        except httpx.TimeoutException as exc:
            raise UpstreamError(503, "Wikimedia request timed out") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(502, "Wikimedia request failed") from exc
    if response.status_code in {429, 503}:
        retry_after = response.headers.get("Retry-After")
        raise UpstreamError(503, f"Wikimedia is unavailable; retry after {retry_after or 'a short delay'}")
    if response.status_code == 404:
        raise UpstreamError(404, "Wikimedia resource was not found")
    if response.is_error:
        raise UpstreamError(502, "Wikimedia returned an unexpected response")
    try:
        payload = response.json()
    except ValueError as exc:
        raise UpstreamError(502, "Wikimedia returned invalid JSON") from exc
    if payload.get("error"):
        error = payload["error"]
        raise UpstreamError(503 if error.get("code") == "maxlag" else 502, "Wikimedia could not process the request")
    return payload


async def hydrate(
    request: Request,
    titles: list[str],
    *,
    example_id: str,
    description: str,
    endpoint: str,
    parameters: dict[str, Any],
    discovery: dict[str, dict[str, Any]] | None = None,
    anchor: str | None = None,
    shortfall_note: str | None = None,
) -> StoredResponse:
    unique_titles = list(dict.fromkeys(title for title in titles if title))[:MAX_PAGES]
    metadata = await upstream_json(
        request,
        ACTION_API,
        _action(
            titles="|".join(unique_titles), redirects=1,
            prop="info|pageterms|pageprops", inprop="url", wbptterms="description",
        ),
    ) if unique_titles else {"query": {"pages": []}}
    by_title = {page.get("title"): page for page in _pages(metadata) if page.get("pageid")}
    records: list[dict[str, Any]] = []
    for title in unique_titles:
        page = by_title.get(title)
        if not page:
            continue
        extract = await upstream_json(
            request, ACTION_API,
            _action(
                titles=title,
                redirects=1,
                prop="extracts|revisions",
                explaintext=1,
                exsectionformat="plain",
                rvprop="ids|timestamp",
                rvlimit=1,
            ),
        )
        extracted_page = next((item for item in _pages(extract) if item.get("pageid")), None)
        text = (extracted_page or {}).get("extract", "")
        if not text:
            continue
        revisions = (extracted_page or {}).get("revisions", [])
        terms = page.get("terms", {}).get("description", [])
        records.append({
            "rank": len(records) + 1,
            "discovery": (discovery or {}).get(title, {"source": example_id}),
            "identity": {
                "wiki": f"{LANGUAGE}wiki", "page_id": page["pageid"], "title": page["title"],
                "canonical_url": page.get("canonicalurl") or page.get("fullurl"),
                "revision_id": revisions[0]["revid"], "revision_timestamp": revisions[0]["timestamp"],
            },
            "card": {
                "description": terms[0] if terms else None,
                "wikidata_id": page.get("pageprops", {}).get("wikibase_item"),
                "length_bytes": page.get("length", 0), "last_touched": page["touched"],
                "is_disambiguation": "disambiguation" in page.get("pageprops", {}),
            },
            "content": {"full_plain_text": text},
        })
    # The shared schema reserves ``shortfall=False`` for complete ten-page
    # envelopes. A caller who asks for fewer than ten pages therefore receives
    # an explicit, valid shortfall envelope rather than an invalid response.
    shortfall = len(records) < MAX_PAGES
    if shortfall and shortfall_note is None:
        shortfall_note = (
            f"Requested {len(unique_titles)} page(s); the shared schema's complete collection size is {MAX_PAGES}"
        )
    dataset = PageResultsDataset.model_validate({
        "schema_version": "1.0.0", "example_id": example_id, "description": description,
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "wiki": f"{LANGUAGE}wiki",
        "source": {"endpoint": endpoint, "parameters": parameters},
        "expansion": {"mode": "natural", "anchor": anchor, "shortfall": shortfall,
                      "note": shortfall_note if shortfall else None},
        "result_count": len(records), "pages": records,
    })
    try:
        await asyncio.to_thread(write_raw_article, dataset)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the raw article dataset") from exc
    return StoredResponse()


async def titles_from_action(request: Request, params: dict[str, Any], limit: int) -> list[str]:
    payload = await upstream_json(request, ACTION_API, params)
    return [page["title"] for page in _pages(payload) if page.get("title")][:limit]


async def category_round_robin(request: Request, prefix: str, count: int, *, mode: Literal["index", "name"]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    if mode == "index":
        payload = await upstream_json(request, ACTION_API, _action(list="allcategories", acprefix=prefix, aclimit=10))
        categories = [f"Category:{item.get('category') or item.get('*')}" for item in payload.get("query", {}).get("allcategories", [])]
    else:
        payload = await upstream_json(request, ACTION_API, _action(list="prefixsearch", pssearch=prefix, psnamespace=14, pslimit=10))
        categories = [item["title"] for item in payload.get("query", {}).get("prefixsearch", [])]
    members: dict[str, list[str]] = {}
    for category in categories[:10]:
        rows = await titles_from_action(request, _action(generator="categorymembers", gcmtitle=category, gcmtype="page", gcmlimit=10, prop="info"), 10)
        members[category] = rows
    selected = round_robin_category_articles(members, count)
    return [title for _, title in selected], {title: {"source_category": category} for category, title in selected}


def collection_count(count: int = Query(10, ge=1, le=10)) -> int:
    return count


@app.get("/v1/random", response_model=StoredResponse)
async def random_pages(request: Request, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    titles = await titles_from_action(request, _action(generator="random", grnnamespace=0, grnlimit=count, prop="info"), count)
    return await hydrate(request, titles, example_id="random-pages", description="Live random pages", endpoint=ACTION_API, parameters={"count": count})


@app.get("/v1/most-viewed/day", response_model=StoredResponse)
async def most_viewed_day(request: Request, day: date, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    url = f"{ANALYTICS}/{LANGUAGE}.wikipedia/all-access/{day.year}/{day.month:02d}/{day.day:02d}"
    payload = await upstream_json(request, url)
    titles = [row["article"].replace("_", " ") for row in payload["items"][0]["articles"][:count]]
    return await hydrate(request, titles, example_id="most-viewed-day", description="Live daily most-viewed pages", endpoint=url, parameters={"day": day.isoformat(), "count": count})


@app.get("/v1/most-viewed/month", response_model=StoredResponse)
async def most_viewed_month(request: Request, year: int = Query(ge=2008), month: int = Query(ge=1, le=12), count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    url = f"{ANALYTICS}/{LANGUAGE}.wikipedia/all-access/{year}/{month:02d}/all-days"
    payload = await upstream_json(request, url)
    titles = [row["article"].replace("_", " ") for row in payload["items"][0]["articles"][:count]]
    return await hydrate(request, titles, example_id="most-viewed-month", description="Live monthly most-viewed pages", endpoint=url, parameters={"year": year, "month": month, "count": count})


@app.get("/v1/most-viewed/year", response_model=StoredResponse)
async def most_viewed_year(request: Request, year: int = Query(ge=2008), count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    today = date.today()
    last_month = 12 if year < today.year else max(today.month - 1, 1)
    scores: dict[str, int] = {}
    for month in range(1, last_month + 1):
        url = f"{ANALYTICS}/{LANGUAGE}.wikipedia/all-access/{year}/{month:02d}/all-days"
        payload = await upstream_json(request, url)
        for rank, article in enumerate(payload.get("items", [{}])[0].get("articles", []), start=1):
            title = article.get("article", "").replace("_", " ")
            scores[title] = scores.get(title, 0) + max(1, 101 - rank)
    titles = [title for title, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:count]]
    return await hydrate(request, titles, example_id="most-viewed-year", description="Aggregated live yearly most-viewed pages", endpoint=ANALYTICS, parameters={"year": year, "count": count, "months": last_month})


@app.get("/v1/categories", response_model=StoredResponse)
async def categories(request: Request, prefix: str, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    titles, discovery = await category_round_robin(request, prefix, count, mode="index")
    return await hydrate(request, titles, example_id="all-categories", description="Round-robin category articles", endpoint=ACTION_API, parameters={"prefix": prefix, "count": count}, discovery=discovery, anchor=prefix, shortfall_note="Not enough distinct category members")


@app.get("/v1/categories/name", response_model=StoredResponse)
async def category_name_search(request: Request, prefix: str, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    titles, discovery = await category_round_robin(request, prefix, count, mode="name")
    return await hydrate(request, titles, example_id="category-name-search", description="Round-robin category-name search articles", endpoint=ACTION_API, parameters={"prefix": prefix, "count": count}, discovery=discovery, anchor=prefix, shortfall_note="Not enough distinct category members")


@app.get("/v1/categories/members", response_model=StoredResponse)
async def category_members(request: Request, category: str, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    category = category if category.startswith("Category:") else f"Category:{category}"
    titles = await titles_from_action(request, _action(generator="categorymembers", gcmtitle=category, gcmtype="page", gcmlimit=count, prop="info"), count)
    return await hydrate(request, titles, example_id="category-members", description="Live category members", endpoint=ACTION_API, parameters={"category": category, "count": count}, anchor=category)


@app.get("/v1/categories/subcategories", response_model=StoredResponse)
async def category_subcategories(request: Request, category: str, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    category = category if category.startswith("Category:") else f"Category:{category}"
    payload = await upstream_json(request, ACTION_API, _action(generator="categorymembers", gcmtitle=category, gcmtype="subcat", gcmlimit=10, prop="info"))
    subcategories = [page["title"] for page in _pages(payload) if page.get("title")]
    members: dict[str, list[str]] = {}
    for subcategory in subcategories:
        members[subcategory] = await titles_from_action(request, _action(generator="categorymembers", gcmtitle=subcategory, gcmtype="page", gcmlimit=10, prop="info"), 10)
    selected = round_robin_category_articles(members, count)
    titles = [title for _, title in selected]
    discovery = {title: {"source_category": source} for source, title in selected}
    return await hydrate(request, titles, example_id="category-subcategories", description="Live subcategory articles", endpoint=ACTION_API, parameters={"category": category, "count": count}, discovery=discovery, anchor=category, shortfall_note="Not enough distinct subcategory members")


@app.get("/v1/nearby", response_model=StoredResponse)
async def nearby(request: Request, latitude: float, longitude: float, radius_m: int = Query(10000, ge=10, le=10000), count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    titles = await titles_from_action(request, _action(generator="geosearch", ggscoord=f"{latitude}|{longitude}", ggsradius=radius_m, ggslimit=count, prop="coordinates"), count)
    return await hydrate(request, titles, example_id="nearby", description="Live nearby pages", endpoint=ACTION_API, parameters={"latitude": latitude, "longitude": longitude, "radius_m": radius_m, "count": count})


@app.get("/v1/featured", response_model=StoredResponse)
async def featured(request: Request, day: date) -> PageResultsDataset:
    url = f"{FEED}/featured/{day.year}/{day.month:02d}/{day.day:02d}"
    payload = await upstream_json(request, url)
    title = _title(payload.get("tfa", {}))
    return await hydrate(request, [title] if title else [], example_id="featured", description="Live featured article", endpoint=url, parameters={"day": day.isoformat()}, anchor=day.isoformat(), shortfall_note="No featured article was available")


@app.get("/v1/on-this-day", response_model=StoredResponse)
async def on_this_day(request: Request, month: int = Query(ge=1, le=12), day: int = Query(ge=1, le=31), event_type: Literal["all", "selected", "events", "births", "deaths", "holidays"] = "all", count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    url = f"{FEED}/onthisday/{event_type}/{month:02d}/{day:02d}"
    payload = await upstream_json(request, url)
    titles: list[str] = []
    for event in payload.get("selected", []) + payload.get("events", []) + payload.get("births", []) + payload.get("deaths", []):
        titles.extend(_title(page) for page in event.get("pages", []))
    return await hydrate(request, [title for title in titles if title][:count], example_id="on-this-day", description="Live on-this-day articles", endpoint=url, parameters={"month": month, "day": day, "type": event_type, "count": count})


@app.get("/v1/search", response_model=StoredResponse)
async def full_text_search(request: Request, query: str, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    titles = await titles_from_action(request, _action(generator="search", gsrsearch=query, gsrlimit=count, gsrnamespace=0, prop="info"), count)
    return await hydrate(request, titles, example_id="full-text-search", description="Live full-text search", endpoint=ACTION_API, parameters={"query": query, "count": count})


@app.get("/v1/search/hydrated", response_model=StoredResponse)
async def hydrated_search(request: Request, query: str, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    titles = await titles_from_action(request, _action(generator="search", gsrsearch=query, gsrlimit=count, gsrnamespace=0, prop="info"), count)
    return await hydrate(request, titles, example_id="hydrated-search", description="Live hydrated search", endpoint=ACTION_API, parameters={"query": query, "count": count})


@app.get("/v1/related", response_model=StoredResponse)
async def related(request: Request, title: str, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    titles = await titles_from_action(request, _action(generator="search", gsrsearch=f"morelike:{title.replace(' ', '_')}", gsrlimit=count, gsrnamespace=0, prop="info"), count)
    return await hydrate(request, titles, example_id="related", description="Live related pages", endpoint=ACTION_API, parameters={"title": title, "count": count}, anchor=title)


@app.get("/v1/prefix/action", response_model=StoredResponse)
async def prefix_action(request: Request, prefix: str, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    titles = await titles_from_action(request, _action(generator="prefixsearch", gpssearch=prefix, gpsnamespace=0, gpslimit=count, prop="info"), count)
    return await hydrate(request, titles, example_id="prefix-action", description="Live Action API prefix search", endpoint=ACTION_API, parameters={"prefix": prefix, "count": count})


@app.get("/v1/prefix/core", response_model=StoredResponse)
async def prefix_core(request: Request, prefix: str, count: int = Query(10, ge=1, le=10)) -> PageResultsDataset:
    url = f"{CORE_REST}/search/page?q={quote(prefix)}&limit={count}"
    payload = await upstream_json(request, url)
    titles = [_title(page) for page in payload.get("pages", [])]
    return await hydrate(request, [title for title in titles if title], example_id="prefix-core-rest", description="Live Core REST prefix search", endpoint=url, parameters={"prefix": prefix, "count": count})


async def single_page(request: Request, title: str, example_id: str, description: str) -> PageResultsDataset:
    return await hydrate(request, [title], example_id=example_id, description=description, endpoint=ACTION_API, parameters={"title": title}, anchor=title)


@app.get("/v1/page-card", response_model=StoredResponse)
async def page_card(request: Request, title: str) -> PageResultsDataset:
    return await single_page(request, title, "page-card-hydration", "Live page-card hydration")


@app.get("/v1/content/intro", response_model=StoredResponse)
async def content_intro(request: Request, title: str) -> PageResultsDataset:
    return await single_page(request, title, "content-intro", "Live intro content")


@app.get("/v1/content/full-text", response_model=StoredResponse)
async def content_full_text(request: Request, title: str) -> PageResultsDataset:
    return await single_page(request, title, "content-full-text", "Live full-text content")


@app.get("/v1/content/section", response_model=StoredResponse)
async def content_section(request: Request, title: str) -> PageResultsDataset:
    return await single_page(request, title, "content-section", "Live parsed-section content")


@app.get("/v1/content/html", response_model=StoredResponse)
async def content_html(request: Request, title: str) -> PageResultsDataset:
    return await single_page(request, title, "content-html", "Live HTML-derived plain-text content")


@app.get("/v1/content/properties", response_model=StoredResponse)
async def content_properties(request: Request, title: str) -> PageResultsDataset:
    return await single_page(request, title, "other-page-properties", "Live other page properties")


@app.exception_handler(UpstreamError)
async def upstream_error_handler(_: Request, exc: UpstreamError) -> HTTPException:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
