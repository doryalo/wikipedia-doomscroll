# Backend

```bash
poetry install
poetry run uvicorn app.main:app --reload
```

Health checks: `GET /live` and `GET /ready`.

## Wikipedia enrichment

Each input file may contain one article:

```json
{
  "id": "ada-lovelace",
  "title": "Ada Lovelace",
  "url": "https://en.wikipedia.org/wiki/Ada_Lovelace",
  "text": "Article text..."
}
```

The enrichment runner also accepts `page-results.schema.json` version `1.0.0` files.
It enriches every item in `pages`, using `<wiki>:<page_id>` as the stable article ID
and `content.full_plain_text` as the source text.

Create a local `.env` file, then run:

```bash
cp .env.example .env
# Edit .env and replace the placeholder with your API key.
```

`.env` is ignored by Git. Existing shell environment variables take precedence over
values in the file.

`ENRICHMENT_INPUT_DIR` defaults to `data/raw-articles`. When the API starts it scans
that directory in the background, then watches for added, modified, or deleted JSON
files. Each change triggers a serial rescan; files are deleted only after every
article they contain is successfully ingested or already current. A second
background worker turns each new current enrichment into one first-person post and
reuses an existing fictional character with the same name.

Then run:

```bash
poetry run python -m app.enrich ./raw-articles
poetry run python -m app.enrich ./raw-articles --force --limit 10
```

The default database is `data/app.db`; override it with `--db PATH`. The command
imports the original JSON, performs evidence extraction with `gpt-5.6-luna`, then
discovery synthesis with `gpt-5.6-terra`, then deletes the file. A file with a failed
article remains for retry; unchanged articles are skipped unless `--force` is supplied.

SQLite is migrated automatically. `current_article_enrichments` exposes the active
analysis and tags; `enrichment_runs` retains history, and `llm_calls` records request
IDs, failures, latency, token usage, pricing rates, and estimated cost.

Generated posts are stored in `posts`, linked to both `articles` and the exact
`enrichment_runs` row that produced them. The normalized tag slugs are copied to the
post's `tags` JSON array. Generation uses `gpt-5.6-terra`; failed runs are logged and
retried when the server restarts.

### Enrichment API

- `GET /enrichments` — paginated current enrichments.
- `GET /enrichments/{article_id}` — the complete current dossier and synthesis.
- `GET /tags` — current tag catalog with article counts.
- `GET /tags/{kind}/{slug}/enrichments` — current enrichments carrying a tag.
- `GET /posts/{post_id}/enrichment` — enrichment linked by `posts.article_id`, with
  `source_url` fallback for older posts.

List endpoints accept `limit` and `offset`; `limit` is capped at 100.

Run the offline test suite with:

```bash
poetry run python -m unittest discover -s tests
```
