import base64
import binascii
import json
from contextlib import closing

from fastapi import APIRouter, HTTPException, Query

from .db import connect, is_ready

router = APIRouter()


@router.get("/live", tags=["health"])
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", tags=["health"])
async def ready() -> dict[str, str]:
    if not is_ready():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}


def _decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        padded_cursor = cursor + "=" * (-len(cursor) % 4)
        payload = base64.urlsafe_b64decode(padded_cursor).decode()
        created_at, post_id = json.loads(payload)
        if not isinstance(created_at, str) or not isinstance(post_id, str):
            raise ValueError
        return created_at, post_id
    except (ValueError, TypeError, UnicodeDecodeError, binascii.Error):
        raise HTTPException(status_code=400, detail="invalid cursor") from None


def _encode_cursor(created_at: str, post_id: str) -> str:
    payload = json.dumps([created_at, post_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


@router.get("/feed", tags=["feed"])
async def feed(
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, object]:
    """Return newest posts first, using a stable createdAt/id cursor."""
    cursor_created_at, cursor_post_id = _decode_cursor(cursor) if cursor else (None, None)

    with closing(connect()) as connection:
        rows = connection.execute(
            """
            SELECT
                posts.*,
                fictional_characters.name AS profile_name,
                fictional_characters.profile_photo_url,
                (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS likes_count,
                (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id) AS comments_count
            FROM posts
            JOIN fictional_characters ON fictional_characters.id = posts.fictional_character_id
            WHERE (
                :cursor_created_at IS NULL
                OR posts.created_at < :cursor_created_at
                OR (posts.created_at = :cursor_created_at AND posts.id < :cursor_post_id)
            )
            ORDER BY posts.created_at DESC, posts.id DESC
            LIMIT :row_limit
            """,
            {
                "cursor_created_at": cursor_created_at,
                "cursor_post_id": cursor_post_id,
                "row_limit": limit + 1,
            },
        ).fetchall()

    has_next_page = len(rows) > limit
    page_rows = rows[:limit]
    items = [_feed_post(row) for row in page_rows]
    next_cursor = (
        _encode_cursor(page_rows[-1]["created_at"], page_rows[-1]["id"])
        if has_next_page and page_rows
        else None
    )
    return {"items": items, "nextCursor": next_cursor}


def _feed_post(row: object) -> dict[str, object]:
    post = dict(row)
    historical_date: dict[str, object] = {
        "startYear": post["historical_start_year"],
        "precision": post["historical_precision"],
        "label": post["historical_date_label"],
    }
    if post["historical_end_year"] is not None:
        historical_date["endYear"] = post["historical_end_year"]

    item: dict[str, object] = {
        "id": post["id"],
        "profileId": post["fictional_character_id"],
        "profileName": post["profile_name"],
        "profilePhotoUrl": post["profile_photo_url"],
        "contentType": post["content_type"],
        "contentText": post["content"],
        "historicalDate": historical_date,
        "createdAt": post["created_at"],
        "tags": json.loads(post["tags"]),
        "likesCount": post["likes_count"],
        "commentsCount": post["comments_count"],
        "sharesCount": 0,
    }
    if post["content_type"] == "image":
        item["contentImageUrl"] = post["media_url"]
    elif post["content_type"] in ("video", "reel"):
        item["contentVideoUrl"] = post["media_url"]
    if post["thumbnail_url"] is not None:
        item["thumbnailUrl"] = post["thumbnail_url"]
    if post["source_url"] is not None:
        item["sourceUrl"] = post["source_url"]
    if post["source_title"] is not None:
        item["sourceTitle"] = post["source_title"]
    return item
