"""Non-blocking image generation for posts that do not yet have media."""

from __future__ import annotations

import base64
import asyncio
import json
import logging
import os
import random
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from openai import OpenAI

from .db import DATABASE_PATH, connect, migrate

logger = logging.getLogger(__name__)
RAW_IMAGES_DIR = Path(__file__).resolve().parent.parent / "data" / "raw-images"
POLL_SECONDS = 2
MAX_IN_FLIGHT = 10
IMAGE_STYLES = (
    ("provocative", "A bold, high-stakes editorial reconstruction that foregrounds conflict, power, and consequence."),
    ("rage-bait", "A deliberately confrontational but fact-grounded visual framing that makes a reader stop and question the historical power dynamic."),
    ("controversial", "A tense, debate-provoking historical scene that presents competing stakes without inventing facts or taking a partisan side."),
    ("poetic", "A cinematic, poetic and emotionally resonant realistic reconstruction with symbolic atmosphere grounded in the period."),
    ("documentary", "A meticulously realistic museum-quality documentary reconstruction with period-accurate material culture."),
)


def _atomic_write(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=f".{destination.stem}-", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise


def _pending_post_ids(database_path: Path) -> list[str]:
    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id FROM posts
            WHERE media_url IS NULL
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (MAX_IN_FLIGHT,),
        ).fetchall()
    return [row["id"] for row in rows]


def _prompt(post: object) -> tuple[str, str]:
    style_name, style_direction = random.choice(IMAGE_STYLES)
    row = post
    return style_name, "\n".join(
        (
            "Use case: historical-scene",
            "Asset type: social discovery feed image",
            f"Primary request: Create an image for the historical post titled {row['title']!r}.",
            f"Historical context: {row['historical_date_label']}; source topic: {row['source_title'] or row['title']}.",
            f"Post context: {row['content']}",
            f"Creative direction: {style_direction}",
            "Style/medium: photorealistic historical reconstruction, cinematic editorial photography.",
            "Constraints: portray only historically plausible people, objects, architecture, clothing, and environment; no modern objects; no text, logos, watermark, or captions.",
        )
    )


def generate_post_image(post_id: str, database_path: Path = DATABASE_PATH) -> None:
    """Generate and attach one image. Called from a detached worker task."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for automatic post images")
    with connect(database_path) as connection:
        migrate(connection)
        post = connection.execute(
            "SELECT id, title, content, historical_date_label, source_title, media_url FROM posts WHERE id = ?",
            (post_id,),
        ).fetchone()
    if post is None or post["media_url"] is not None:
        return

    style, prompt = _prompt(post)
    response = OpenAI().images.generate(model="gpt-image-2", prompt=prompt)
    encoded = response.data[0].b64_json
    if not encoded:
        raise RuntimeError("OpenAI returned no image content")
    image = base64.b64decode(encoded, validate=True)
    media_id = uuid4().hex
    _atomic_write(RAW_IMAGES_DIR / f"{media_id}.png", image)
    _atomic_write(
        RAW_IMAGES_DIR / "debug" / f"{media_id}.json",
        json.dumps(
            {
                "media_id": media_id,
                "post_id": post_id,
                "kind": "image",
                "model": "gpt-image-2",
                "style": style,
                "status": "completed",
                "created_at": datetime.now(UTC).isoformat(),
                "prompt": prompt,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode(),
    )
    media_url = f"/v1/media/{media_id}"
    with connect(database_path) as connection:
        connection.execute(
            """
            UPDATE posts
            SET media_url = ?, thumbnail_url = ?, content_type = 'image'
            WHERE id = ? AND media_url IS NULL
            """,
            (media_url, media_url, post_id),
        )
    logger.info("post_image.done post_id=%s media_url=%s style=%s", post_id, media_url, style)


async def watch_post_images(
    database_path: Path = DATABASE_PATH, *, poll_seconds: float = POLL_SECONDS
) -> None:
    """Schedule image work without awaiting it from the post creation path."""
    in_flight: set[str] = set()

    async def run(post_id: str) -> None:
        try:
            await asyncio.to_thread(generate_post_image, post_id, database_path)
        except Exception:
            logger.exception("post_image.failed post_id=%s", post_id)
        finally:
            in_flight.discard(post_id)

    while True:
        if os.getenv("OPENAI_API_KEY"):
            for post_id in await asyncio.to_thread(_pending_post_ids, database_path):
                if post_id not in in_flight:
                    in_flight.add(post_id)
                    asyncio.create_task(run(post_id))
        await asyncio.sleep(poll_seconds)
