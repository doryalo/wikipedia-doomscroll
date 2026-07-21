# OpenAI Media Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add post-scoped OpenAI image and Sora reel generation routes that persist artifacts and metadata beneath `backend/data/raw-articles/media/`.

**Architecture:** Keep the existing Wikimedia client and raw-article handoff unchanged. Extend `wikimedia_api/main.py` with a lifespan-managed `AsyncOpenAI` client, typed media DTOs, filesystem helpers, and three media route groups: immediate image generation, asynchronous reel start/status, and completed-artifact serving. A sidecar JSON is the durable post-to-media association; no post database lookup occurs.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, OpenAI Python SDK 2.x, `gpt-image-2`, `sora-2`, `asyncio.to_thread`, `FileResponse`, unittest with fake OpenAI clients.

---

## File structure

- `wikimedia_api/main.py` owns the public media DTOs, prompt composition, OpenAI calls, atomic file/sidecar persistence, and the routes. It must keep the existing Wikimedia-only request coordinator and raw-article writer intact.
- `backend/pyproject.toml` already declares `openai>=2,<3`; do not change its version range unless the installed SDK lacks the documented async methods.
- `wikimedia_api/test_media_generation.py` is a deterministic focused regression suite. It imports the app helpers, injects fake OpenAI resources, and writes only to a temporary directory.
- `docs/superpowers/specs/2026-07-21-openai-media-generation-design.md` records the exact model choices, artifact layout, Sora deprecation date, and route contract.

### Task 1: Add media DTOs and filesystem-safe persistence helpers

**Files:**
- Modify: `wikimedia_api/main.py`
- Create: `wikimedia_api/test_media_generation.py`

- [ ] **Step 1: Write the failing storage and prompt-contract tests**

```python
from pathlib import Path

from wikimedia_api.main import MediaGenerationRequest, compose_media_prompt, write_media_record


def test_media_record_is_post_scoped_and_has_a_sidecar(tmp_path: Path) -> None:
    record = write_media_record(
        directory=tmp_path,
        post_id="post-42",
        media_id="media-abc",
        kind="image",
        extension="png",
        content=b"png-bytes",
        metadata={"status": "completed", "model": "gpt-image-2"},
    )

    assert record.artifact_path == tmp_path / "media" / "post-42" / "media-abc.png"
    assert record.artifact_path.read_bytes() == b"png-bytes"
    assert record.sidecar_path.name == "media-abc.json"
    assert '"post_id": "post-42"' in record.sidecar_path.read_text()


def test_prompt_labels_every_semantic_input() -> None:
    request = MediaGenerationRequest(
        postId="post-42", description="A telescope on a hill",
        logicalValue="Observation changes scientific understanding",
        timeFrame="1609", concept="A threshold to discovery",
        intent="Make viewers curious about astronomy",
    )

    prompt = compose_media_prompt(request, medium="still image")

    for label in ("Description:", "Logical value:", "Time frame:", "Concept:", "Intent:"):
        assert label in prompt
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest wikimedia_api.test_media_generation -v`

Expected: FAIL because `MediaGenerationRequest`, `compose_media_prompt`, and `write_media_record` do not exist.

- [ ] **Step 3: Add the DTOs, prompt builder, and atomic writer**

Add the following adjacent to the existing `RAW_ARTICLE_DIR` constant. Keep the media root nested so the watcher’s non-recursive `glob("*.json")` ignores sidecars.

```python
MEDIA_DIR = RAW_ARTICLE_DIR / "media"
POST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


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


def compose_media_prompt(request: MediaGenerationRequest, *, medium: str) -> str:
    return "\n".join((
        f"Create a {medium}.", f"Description: {request.description}",
        f"Logical value: {request.logical_value}", f"Time frame: {request.time_frame}",
        f"Concept: {request.concept}", f"Intent: {request.intent}",
    ))
```

Implement `write_media_record()` with a caller-generated `media_id`, a private `._tmp` filename in the destination directory, `flush()`, `os.fsync()`, and `os.replace()` for both binary artifact and JSON sidecar. Include the canonical fields `media_id`, `post_id`, `kind`, `status`, `model`, `provider_job_id`, `artifact_filename`, prompt inputs, and UTC timestamps. Never infer a database relationship from the supplied `postId`.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `PYTHONPATH=. python3 -m unittest wikimedia_api.test_media_generation -v`

Expected: PASS; no real API request and no write below the repository’s `backend/data/raw-articles/media/` directory.

- [ ] **Step 5: Commit the TDD slice**

```bash
git add wikimedia_api/main.py wikimedia_api/test_media_generation.py
git commit -m "feat: add post-scoped media storage"
```

### Task 2: Add the OpenAI lifecycle client and synchronous image endpoint

**Files:**
- Modify: `wikimedia_api/main.py`
- Modify: `wikimedia_api/test_media_generation.py`

- [ ] **Step 1: Write the failing fake-client endpoint test**

```python
from base64 import b64encode
from fastapi.testclient import TestClient

from wikimedia_api.main import app


class FakeImages:
    async def generate(self, **kwargs):
        self.kwargs = kwargs
        return type("Response", (), {"data": [type("Image", (), {
            "b64_json": b64encode(b"image-bytes").decode()
        })()]})()


def test_image_generation_persists_a_png_and_returns_post_link(tmp_path):
    app.state.openai = type("OpenAI", (), {"images": FakeImages()})()
    app.state.media_dir = tmp_path
    with TestClient(app) as client:
        response = client.post("/v1/media/images/generations", json={
            "postId": "post-42", "description": "A sundial",
            "logicalValue": "Time can be measured", "timeFrame": "Ancient Rome",
            "concept": "Light marks time", "intent": "Teach the idea simply",
        })
    assert response.status_code == 201
    body = response.json()
    assert body["postId"] == "post-42"
    assert (tmp_path / "post-42" / f'{body["mediaId"]}.png').read_bytes() == b"image-bytes"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest wikimedia_api.test_media_generation.MediaEndpointTests.test_image_generation_persists_a_png_and_returns_post_link -v`

Expected: FAIL because the image generation route is absent.

- [ ] **Step 3: Implement client lifecycle and route**

Import `AsyncOpenAI`, `APIConnectionError`, `APIStatusError`, and `RateLimitError` from `openai`; import `base64`, `Field`, and `field_validator` for the new helpers. In the existing lifespan, construct `AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))` only when the key is configured, save it as `app.state.openai`, and close it during shutdown. Do not alter `app.state.client`, the Wikimedia headers, or `UpstreamCoordinator`.

Add `POST /v1/media/images/generations`, status `201`. It must:

1. reject the request with `503` if the OpenAI client is unavailable;
2. call `await request.app.state.openai.images.generate(model="gpt-image-2", prompt=compose_media_prompt(...))`;
3. base64-decode `data[0].b64_json` and atomically write the PNG plus completed sidecar;
4. return `mediaId`, `postId`, `kind: "image"`, `status: "completed"`, model, and `/v1/media/artifacts/{postId}/{mediaId}`;
5. map provider moderation failures to `422`, rate limits to `503`, and connection/status failures to `502`/`503` without including provider bodies or credentials.

- [ ] **Step 4: Run the image endpoint tests to verify they pass**

Run: `PYTHONPATH=. python3 -m unittest wikimedia_api.test_media_generation -v`

Expected: PASS; the fake client receives `gpt-image-2` and the persisted sidecar records the request fields.

- [ ] **Step 5: Commit the image route**

```bash
git add wikimedia_api/main.py wikimedia_api/test_media_generation.py
git commit -m "feat: generate post-scoped images"
```

### Task 3: Add Sora reel creation, persisted status, and artifact serving

**Files:**
- Modify: `wikimedia_api/main.py`
- Modify: `wikimedia_api/test_media_generation.py`

- [ ] **Step 1: Write the failing reel and artifact tests**

```python
def test_reel_start_writes_queued_sidecar_and_returns_status_url(tmp_path):
    app.state.openai = type("OpenAI", (), {"videos": FakeVideos("video-provider-1", "queued")})()
    app.state.media_dir = tmp_path
    with TestClient(app) as client:
        response = client.post("/v1/media/reels/generations", json=VALID_MEDIA_BODY)
    assert response.status_code == 202
    body = response.json()
    assert body["providerJobId"] == "video-provider-1"
    assert body["status"] == "queued"
    assert body["statusUrl"].endswith("video-provider-1")


def test_completed_reel_status_downloads_mp4_and_artifact_route_serves_it(tmp_path):
    write_media_record(tmp_path, "post-42", "media-abc", "reel", "mp4", None, {
        "status": "queued", "provider_job_id": "video-provider-1", "model": "sora-2"
    })
    app.state.openai = type("OpenAI", (), {"videos": CompletedFakeVideos()})()
    app.state.media_dir = tmp_path
    with TestClient(app) as client:
        status = client.get("/v1/media/reels/generations/video-provider-1")
        artifact = client.get("/v1/media/artifacts/post-42/media-abc")
    assert status.json()["status"] == "completed"
    assert artifact.content == b"mp4-bytes"
    assert artifact.headers["content-type"].startswith("video/mp4")
```

- [ ] **Step 2: Run the reel tests to verify they fail**

Run: `PYTHONPATH=. python3 -m unittest wikimedia_api.test_media_generation.MediaEndpointTests.test_reel_start_writes_queued_sidecar_and_returns_status_url wikimedia_api.test_media_generation.MediaEndpointTests.test_completed_reel_status_downloads_mp4_and_artifact_route_serves_it -v`

Expected: FAIL because the reel creation, status, and artifact routes are absent.

- [ ] **Step 3: Implement reel and artifact routes**

Add these routes without calling the post database:

1. `POST /v1/media/reels/generations` returns `202`, calls `await openai.videos.create(model="sora-2", prompt=compose_media_prompt(...), size="720x1280", seconds="8")`, writes a queued sidecar, and returns `mediaId`, `postId`, `providerJobId`, `status`, and the backend status URL. Include a code comment that Sora 2/Videos API is deprecated and scheduled for shutdown on 2026-09-24.
2. `GET /v1/media/reels/generations/{job_id}` finds the nested sidecar by provider job ID, calls `await openai.videos.retrieve(job_id)`, updates status/progress/model atomically, and when completed downloads bytes with `await openai.videos.download_content(job_id)` before publishing the MP4. Return `404` for an unknown local job, preserving the rule that the backend only surfaces jobs it created.
3. `GET /v1/media/artifacts/{post_id}/{media_id}` applies the same filesystem-safe ID rule, loads the local sidecar, rejects missing/queued/failed artifacts with `404`/`409`, and uses `FileResponse` with `image/png` or `video/mp4`. Do not accept a filename, extension, or arbitrary path from the caller.

For restart-safe lookup, search only `app.state.media_dir.glob("*/*.json")`, parse sidecars defensively, and match `provider_job_id`; never scan or parse direct `backend/data/raw-articles/*.json` envelopes.

- [ ] **Step 4: Run the full media suite to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest wikimedia_api.test_media_generation -v`

Expected: PASS with deterministic fake client calls, no network traffic, and image/reel artifacts confined to the temporary media root.

- [ ] **Step 5: Commit the reel and artifact routes**

```bash
git add wikimedia_api/main.py wikimedia_api/test_media_generation.py
git commit -m "feat: persist generated reels by post"
```

### Task 4: Verify the integrated API contract and preserve existing routes

**Files:**
- Modify: `wikimedia_api/test_media_generation.py`
- Modify: `docs/superpowers/specs/2026-07-21-openai-media-generation-design.md`

- [ ] **Step 1: Write the OpenAPI regression test**

```python
def test_openapi_exposes_all_media_contracts() -> None:
    paths = app.openapi()["paths"]
    assert "/v1/media/images/generations" in paths
    assert "/v1/media/reels/generations" in paths
    assert "/v1/media/reels/generations/{job_id}" in paths
    assert "/v1/media/artifacts/{post_id}/{media_id}" in paths
    assert "/v1/random" in paths
```

- [ ] **Step 2: Run the test to verify it fails or detects OpenAPI drift**

Run: `PYTHONPATH=. python3 -m unittest wikimedia_api.test_media_generation.MediaContractTests.test_openapi_exposes_all_media_contracts -v`

Expected: FAIL until every media route is registered with a concrete response model.

- [ ] **Step 3: Add concrete response models and documentation note**

Define Pydantic response models for completed images, queued/reel status, and artifacts instead of returning untyped dictionaries. Update the design spec only if the implemented route field names differ from the approved contract. Retain the Sora shutdown warning and do not add a frontend API key constant.

- [ ] **Step 4: Run the complete focused verification set**

Run: `PYTHONPATH=. python3 -m unittest wikimedia_api.test_media_generation -v`

Expected: all media tests PASS.

Run: `python3 -m py_compile wikimedia_api/main.py`

Expected: exit code `0`.

Run: `PYTHONPATH=. python3 -c 'from wikimedia_api.main import app; print(sorted(path for path in app.openapi()["paths"] if path.startswith("/v1/media/")))'`

Expected: the four documented media paths print and existing `/v1/...` routes remain in the schema.

- [ ] **Step 5: Commit the contract verification**

```bash
git add wikimedia_api/main.py wikimedia_api/test_media_generation.py docs/superpowers/specs/2026-07-21-openai-media-generation-design.md
git commit -m "test: verify OpenAI media API contract"
```
