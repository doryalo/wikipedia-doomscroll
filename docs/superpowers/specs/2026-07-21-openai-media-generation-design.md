# OpenAI Media Generation Design

## Goal

Add OpenAI-backed image and short-reel generation to the development-facing
FastAPI adapter in `wikimedia_api/main.py`. Each generated media result is
persisted under the caller-supplied post identifier; it does not create,
validate, or modify a feed post.

## Scope

- Add `POST /v1/media/images/generations` for a one-shot image generation.
- Add `POST /v1/media/reels/generations` to start an asynchronous Sora render.
- Add `GET /v1/media/reels/generations/{job_id}` to retrieve render status and
  completed MP4 metadata without exposing the OpenAI key to the client.
- Add `GET /v1/media/artifacts/{post_id}/{media_id}` to serve a completed
  persisted PNG or MP4 from its post-scoped storage directory.
- Use the OpenAI Python SDK, `gpt-image-2` for images, and `sora-2` for reels.
- Sora 2 and the Videos API are scheduled by OpenAI to shut down on September
  24, 2026. Keep the Sora client isolated behind a small adapter so its
  replacement does not alter the route contract or media storage layout.
- Read `OPENAI_API_KEY` exclusively from the server environment. Do not put a
  credential in source, an API response, or client-side code.
- Store artifacts below `backend/data/raw-articles/media/<post_id>/`. The
  existing raw-article watcher only scans direct `*.json` children of
  `backend/data/raw-articles/`, so this nested media subtree is not treated as
  a Wikimedia input envelope.

## Request contract

Both generation requests require these independent string fields:

- `postId`: an opaque caller-provided post identifier. The API does not query
  the database or otherwise verify that it exists.
- `description`: concrete subject and scene details.
- `logicalValue`: the factual or educational point the visual must convey.
- `timeFrame`: the historical era or present-day setting to represent.
- `concept`: the visual metaphor or creative framing.
- `intent`: the desired viewer outcome, separate from the concept.

The image request may set an image size and quality. The reel request may set
the portrait/landscape size and a supported duration. All fields are passed to
a single labelled prompt template so their roles stay explicit and testable.

`postId` is constrained to a filesystem-safe identifier, but never validated
against a `posts` record. A completed image is written as
`backend/data/raw-articles/media/<post_id>/<media_id>.png`; a completed reel
uses the same directory and a `.mp4` suffix. Each artifact has a sibling
`<media_id>.json` sidecar containing `media_id`, `post_id`, kind, provider
model/job ID, generated relative path, five prompt inputs, status, and
timestamps. The sidecar is the durable association record; the path provides
human-readable grouping only.

## Execution model

Image generation is synchronous: the service calls the Images API, atomically
writes the PNG and its sidecar, then returns the `mediaId`, `postId`, and a
backend artifact URL. A request rejected by provider safety checks is returned
as a stable client-safe error; upstream timeouts, rate limits, and failures
remain safe `502`/`503` errors.

Reel generation is asynchronous: the creation route calls Sora, writes a
queued sidecar, and returns the provider job ID, initial status, and the
adapter status URL. The status route retrieves the current provider state. On
completion it atomically writes the MP4, updates the sidecar, and returns the
backend artifact URL. This avoids a long-running request and keeps the OpenAI
credential private.

## Boundaries

The existing Wikimedia `httpx.AsyncClient`, compliance header, and upstream
coordinator remain Wikimedia-only. OpenAI gets a separate lifespan-managed
`AsyncOpenAI` client. No OpenAI request is sent with the Wikimedia User-Agent,
and no Wikimedia request can use the OpenAI client. This design adds no
database schema or foreign-key validation.

## Verification

Focused tests will inject a fake OpenAI client and verify filesystem-safe
`postId` validation without database access, labelled prompt composition,
atomic artifact and sidecar writes, image response decoding, reel creation,
status mapping, completed-video persistence, and provider error mapping. No
test calls a live OpenAI or Wikimedia API.
