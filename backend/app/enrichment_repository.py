import json
import sqlite3


def list_enrichments(
    connection: sqlite3.Connection, *, limit: int, offset: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT * FROM current_article_enrichments
        ORDER BY completed_at DESC, article_id
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return [_enrichment(row) for row in rows]


def get_enrichment(
    connection: sqlite3.Connection, article_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM current_article_enrichments WHERE article_id = ?",
        (article_id,),
    ).fetchone()
    return _enrichment(row) if row else None


def list_tags(
    connection: sqlite3.Connection, *, limit: int, offset: int
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT t.kind, t.slug, t.label, t.taxonomy_path_json,
               COUNT(DISTINCT at.run_id) AS article_count
        FROM tags AS t
        JOIN article_tags AS at ON at.tag_id = t.id
        JOIN enrichment_runs AS r ON r.id = at.run_id AND r.is_current = 1
        GROUP BY t.id
        ORDER BY article_count DESC, t.kind, t.slug
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return [
        {
            "kind": row["kind"],
            "slug": row["slug"],
            "label": row["label"],
            "taxonomy_path": json.loads(row["taxonomy_path_json"]),
            "article_count": row["article_count"],
        }
        for row in rows
    ]


def list_enrichments_by_tag(
    connection: sqlite3.Connection,
    *,
    kind: str,
    slug: str,
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT current.*
        FROM current_article_enrichments AS current
        JOIN article_tags AS at ON at.run_id = current.enrichment_run_id
        JOIN tags AS t ON t.id = at.tag_id
        WHERE t.kind = ? AND t.slug = ?
        ORDER BY at.rank, current.completed_at DESC
        LIMIT ? OFFSET ?
        """,
        (kind, slug, limit, offset),
    ).fetchall()
    return [_enrichment(row) for row in rows]


def get_post_enrichment(
    connection: sqlite3.Connection, post_id: str
) -> dict[str, object] | None:
    post = connection.execute(
        """
        SELECT id, title, content, article_id, enrichment_run_id, source_url
        FROM posts WHERE id = ?
        """,
        (post_id,),
    ).fetchone()
    if post is None:
        return None
    if post["enrichment_run_id"]:
        enrichment = _get_run_enrichment(connection, post["enrichment_run_id"])
    elif post["article_id"]:
        enrichment = get_enrichment(connection, post["article_id"])
    else:
        row = connection.execute(
            "SELECT * FROM current_article_enrichments WHERE url = ?",
            (post["source_url"],),
        ).fetchone()
        enrichment = _enrichment(row) if row else None
    if enrichment is None:
        return None
    return {
        "post_id": post["id"],
        "post_title": post["title"],
        "post_content": post["content"],
        "enrichment": enrichment,
    }


def _get_run_enrichment(
    connection: sqlite3.Connection, run_id: int
) -> dict[str, object] | None:
    row = connection.execute(
        """
        SELECT a.id AS article_id, a.title, a.url, a.language,
               r.id AS enrichment_run_id, r.schema_version, r.prompt_version,
               r.extraction_model, r.synthesis_model, r.completed_at,
               analysis.extraction_json, analysis.synthesis_json
        FROM enrichment_runs AS r
        JOIN articles AS a ON a.id = r.article_id
        JOIN article_analyses AS analysis ON analysis.run_id = r.id
        WHERE r.id = ? AND r.status = 'succeeded'
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    tags = connection.execute(
        """
        SELECT t.kind, t.slug, t.label, t.taxonomy_path_json,
               article_tags.rank, article_tags.confidence,
               article_tags.rationale, article_tags.evidence_ids_json
        FROM article_tags
        JOIN tags AS t ON t.id = article_tags.tag_id
        WHERE article_tags.run_id = ?
        ORDER BY article_tags.rank
        """,
        (run_id,),
    ).fetchall()
    return _enrichment(
        row,
        tags=[
            {
                "kind": tag["kind"],
                "slug": tag["slug"],
                "label": tag["label"],
                "taxonomy_path": json.loads(tag["taxonomy_path_json"]),
                "rank": tag["rank"],
                "confidence": tag["confidence"],
                "rationale": tag["rationale"],
                "evidence_ids": json.loads(tag["evidence_ids_json"]),
            }
            for tag in tags
        ],
    )


def _enrichment(
    row: sqlite3.Row, *, tags: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "article_id": row["article_id"],
        "title": row["title"],
        "url": row["url"],
        "language": row["language"],
        "enrichment_run_id": row["enrichment_run_id"],
        "schema_version": row["schema_version"],
        "prompt_version": row["prompt_version"],
        "extraction_model": row["extraction_model"],
        "synthesis_model": row["synthesis_model"],
        "completed_at": row["completed_at"],
        "extraction": json.loads(row["extraction_json"]),
        "synthesis": json.loads(row["synthesis_json"]),
        "tags": tags if tags is not None else json.loads(row["tags_json"]),
    }
