import base64
import binascii
import hashlib
import json
import secrets
import sqlite3
from contextlib import closing

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from .db import connect, is_ready, new_id

router = APIRouter()


class LikeRequest(BaseModel):
    profileId: str


class CommentRequest(BaseModel):
    profileId: str
    content: str = Field(min_length=1, max_length=5_000)


class SignupRequest(BaseModel):
    username: str = Field(min_length=2, max_length=30)
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    username: str
    password: str


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    parts = stored.split(":", 1)
    if len(parts) != 2:
        return False
    salt, expected = parts
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return h == expected


POST_SELECT = """
SELECT
    posts.*,
    fictional_characters.name AS profile_name,
    fictional_characters.profile_photo_url,
    (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS likes_count,
    (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id) AS comments_count
FROM posts
JOIN fictional_characters ON fictional_characters.id = posts.fictional_character_id
"""


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
    return _paginated_posts(cursor=cursor, limit=limit)


@router.get("/groups/{group_id}/posts", tags=["groups", "feed"])
async def group_posts(
    group_id: str,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, object]:
    with closing(connect()) as connection:
        group = connection.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")

    return _paginated_posts(
        cursor=cursor,
        limit=limit,
        filter_sql="""
        EXISTS (
            SELECT 1 FROM post_groups
            WHERE post_groups.post_id = posts.id AND post_groups.group_id = :group_id
        )
        """,
        parameters={"group_id": group_id},
    )


@router.get("/posts/{post_id}", tags=["posts"])
async def get_post(post_id: str) -> dict[str, object]:
    rows = _fetch_posts("posts.id = :post_id", {"post_id": post_id}, 1)
    if not rows:
        raise HTTPException(status_code=404, detail="post not found")
    return _feed_post(rows[0])


@router.post("/posts/{post_id}/likes", tags=["posts"])
async def like_post(post_id: str, request: LikeRequest) -> dict[str, bool]:
    with closing(connect()) as connection:
        _require_record(connection, "posts", post_id, "post")
        _require_record(connection, "profiles", request.profileId, "profile")
        connection.execute(
            "INSERT OR IGNORE INTO likes (profile_id, post_id) VALUES (?, ?)",
            (request.profileId, post_id),
        )
        connection.commit()
    return {"liked": True}


@router.post("/posts/{post_id}/comments", tags=["posts"], status_code=status.HTTP_201_CREATED)
async def create_comment(post_id: str, request: CommentRequest) -> dict[str, str]:
    comment_id = new_id()
    with closing(connect()) as connection:
        _require_record(connection, "posts", post_id, "post")
        _require_record(connection, "profiles", request.profileId, "profile")
        connection.execute(
            "INSERT INTO comments (id, profile_id, post_id, content) VALUES (?, ?, ?, ?)",
            (comment_id, request.profileId, post_id, request.content),
        )
        comment = connection.execute(
            "SELECT id, profile_id, content, created_at FROM comments WHERE id = ?", (comment_id,)
        ).fetchone()
        connection.commit()
    return {
        "id": comment["id"],
        "profileId": comment["profile_id"],
        "content": comment["content"],
        "createdAt": comment["created_at"],
    }


@router.get("/posts/{post_id}/likes", tags=["posts"])
async def get_post_likes(post_id: str) -> list[dict[str, str]]:
    with closing(connect()) as connection:
        _require_record(connection, "posts", post_id, "post")
        rows = connection.execute(
            """
            SELECT profiles.id, profiles.username
            FROM likes
            JOIN profiles ON profiles.id = likes.profile_id
            WHERE likes.post_id = ?
            ORDER BY likes.created_at ASC
            """,
            (post_id,),
        ).fetchall()
    return [{"profileId": row["id"], "username": row["username"]} for row in rows]


@router.post("/auth/signup", tags=["auth"], status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest) -> dict[str, str]:
    profile_id = new_id()
    password_hash = _hash_password(request.password)
    with closing(connect()) as connection:
        if connection.execute(
            "SELECT 1 FROM profiles WHERE username = ? COLLATE NOCASE", (request.username,)
        ).fetchone():
            raise HTTPException(status_code=409, detail="username taken")
        connection.execute(
            "INSERT INTO profiles (id, username, password_hash) VALUES (?, ?, ?)",
            (profile_id, request.username, password_hash),
        )
        connection.commit()
    return {"id": profile_id, "username": request.username}


@router.post("/auth/login", tags=["auth"])
async def login(request: LoginRequest) -> dict[str, str]:
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT id, username, password_hash FROM profiles WHERE username = ? COLLATE NOCASE",
            (request.username,),
        ).fetchone()
    if row is None or not _verify_password(request.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"id": row["id"], "username": row["username"]}


def _paginated_posts(
    cursor: str | None,
    limit: int,
    filter_sql: str = "1 = 1",
    parameters: dict[str, str] | None = None,
) -> dict[str, object]:
    cursor_created_at, cursor_post_id = _decode_cursor(cursor) if cursor else (None, None)
    query_parameters = parameters or {}
    query_parameters.update(
        {
            "cursor_created_at": cursor_created_at,
            "cursor_post_id": cursor_post_id,
        }
    )
    rows = _fetch_posts(
        f"""
        ({filter_sql})
        AND (
            :cursor_created_at IS NULL
            OR posts.created_at < :cursor_created_at
            OR (posts.created_at = :cursor_created_at AND posts.id < :cursor_post_id)
        )
        """,
        query_parameters,
        limit + 1,
    )
    has_next_page = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = (
        _encode_cursor(page_rows[-1]["created_at"], page_rows[-1]["id"])
        if has_next_page and page_rows
        else None
    )
    return {"items": [_feed_post(row) for row in page_rows], "nextCursor": next_cursor}


def _fetch_posts(
    where_sql: str, parameters: dict[str, str | None], limit: int
) -> list[sqlite3.Row]:
    with closing(connect()) as connection:
        return connection.execute(
            f"""
            {POST_SELECT}
            WHERE {where_sql}
            ORDER BY posts.created_at DESC, posts.id DESC
            LIMIT :row_limit
            """,
            {**parameters, "row_limit": limit},
        ).fetchall()


def _require_record(
    connection: sqlite3.Connection, table: str, record_id: str, record_name: str
) -> None:
    if connection.execute(f"SELECT 1 FROM {table} WHERE id = ?", (record_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail=f"{record_name} not found")


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
