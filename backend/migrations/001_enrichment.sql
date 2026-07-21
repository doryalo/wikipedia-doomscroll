CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK(length(trim(title)) > 0),
    url TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    text TEXT NOT NULL CHECK(length(trim(text)) > 0),
    raw_json TEXT NOT NULL CHECK(json_valid(raw_json)),
    source_path TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK(length(content_sha256) = 64),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE enrichment_runs (
    id INTEGER PRIMARY KEY,
    article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    content_sha256 TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    prompt_version TEXT NOT NULL,
    extraction_model TEXT NOT NULL,
    synthesis_model TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN (
        'started', 'extracting', 'synthesizing', 'succeeded', 'failed'
    )),
    is_current INTEGER NOT NULL DEFAULT 0 CHECK(is_current IN (0, 1)),
    error_type TEXT,
    error_message TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    CHECK(is_current = 0 OR status = 'succeeded')
);

CREATE TABLE article_analyses (
    run_id INTEGER PRIMARY KEY REFERENCES enrichment_runs(id) ON DELETE CASCADE,
    extraction_json TEXT CHECK(extraction_json IS NULL OR json_valid(extraction_json)),
    synthesis_json TEXT CHECK(synthesis_json IS NULL OR json_valid(synthesis_json))
);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    slug TEXT NOT NULL,
    label TEXT NOT NULL,
    taxonomy_path_json TEXT NOT NULL CHECK(json_valid(taxonomy_path_json)),
    created_at TEXT NOT NULL,
    UNIQUE(kind, slug)
);

CREATE TABLE article_tags (
    run_id INTEGER NOT NULL REFERENCES enrichment_runs(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE RESTRICT,
    rank INTEGER NOT NULL CHECK(rank > 0),
    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
    rationale TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL CHECK(json_valid(evidence_ids_json)),
    PRIMARY KEY(run_id, tag_id)
);

CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY,
    article_id TEXT REFERENCES articles(id) ON DELETE SET NULL,
    enrichment_run_id INTEGER REFERENCES enrichment_runs(id) ON DELETE SET NULL,
    operation TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model TEXT NOT NULL,
    reasoning_effort TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('started', 'succeeded', 'failed')),
    max_retries INTEGER NOT NULL CHECK(max_retries >= 0),
    response_id TEXT,
    request_id TEXT,
    status_code INTEGER,
    latency_ms INTEGER CHECK(latency_ms IS NULL OR latency_ms >= 0),
    input_tokens INTEGER CHECK(input_tokens IS NULL OR input_tokens >= 0),
    cached_input_tokens INTEGER CHECK(cached_input_tokens IS NULL OR cached_input_tokens >= 0),
    output_tokens INTEGER CHECK(output_tokens IS NULL OR output_tokens >= 0),
    reasoning_tokens INTEGER CHECK(reasoning_tokens IS NULL OR reasoning_tokens >= 0),
    total_tokens INTEGER CHECK(total_tokens IS NULL OR total_tokens >= 0),
    pricing_version TEXT,
    input_usd_per_million TEXT,
    cached_input_usd_per_million TEXT,
    output_usd_per_million TEXT,
    estimated_cost_usd TEXT,
    error_type TEXT,
    error_message TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE UNIQUE INDEX one_current_enrichment_per_article
    ON enrichment_runs(article_id) WHERE is_current = 1;
CREATE INDEX enrichment_runs_article_status
    ON enrichment_runs(article_id, status, started_at);
CREATE INDEX tags_kind_slug ON tags(kind, slug);
CREATE INDEX article_tags_tag_id ON article_tags(tag_id, run_id);
CREATE INDEX llm_calls_article_status
    ON llm_calls(article_id, status, started_at);
CREATE INDEX llm_calls_run_id ON llm_calls(enrichment_run_id);

CREATE VIEW current_article_enrichments AS
SELECT
    a.id AS article_id,
    a.title,
    a.url,
    a.language,
    a.text,
    a.raw_json,
    a.content_sha256,
    r.id AS enrichment_run_id,
    r.schema_version,
    r.prompt_version,
    r.extraction_model,
    r.synthesis_model,
    r.completed_at,
    aa.extraction_json,
    aa.synthesis_json,
    COALESCE(
        (
            SELECT json_group_array(
                json_object(
                    'kind', ordered_tags.kind,
                    'slug', ordered_tags.slug,
                    'label', ordered_tags.label,
                    'taxonomy_path', json(ordered_tags.taxonomy_path_json),
                    'rank', ordered_tags.rank,
                    'confidence', ordered_tags.confidence,
                    'rationale', ordered_tags.rationale,
                    'evidence_ids', json(ordered_tags.evidence_ids_json)
                )
            )
            FROM (
                SELECT t.kind, t.slug, t.label, t.taxonomy_path_json,
                       at.rank, at.confidence, at.rationale, at.evidence_ids_json
                FROM article_tags AS at
                JOIN tags AS t ON t.id = at.tag_id
                WHERE at.run_id = r.id
                ORDER BY at.rank
            ) AS ordered_tags
        ),
        json('[]')
    ) AS tags_json
FROM articles AS a
JOIN enrichment_runs AS r ON r.article_id = a.id AND r.is_current = 1
JOIN article_analyses AS aa ON aa.run_id = r.id
WHERE r.status = 'succeeded';
