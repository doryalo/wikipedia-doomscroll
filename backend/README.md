# Backend

```bash
poetry install
poetry run uvicorn app.main:app --reload
```

Health checks: `GET /live` and `GET /ready`.

## Wikipedia enrichment

Each input file must contain one English article:

```json
{
  "id": "ada-lovelace",
  "title": "Ada Lovelace",
  "url": "https://en.wikipedia.org/wiki/Ada_Lovelace",
  "text": "Article text..."
}
```

Create a local `.env` file, then run:

```bash
cp .env.example .env
# Edit .env and replace the placeholder with your API key.
```

`.env` is ignored by Git. Existing shell environment variables take precedence over
values in the file.

Then run:

```bash
poetry run python -m app.enrich ./raw-articles
poetry run python -m app.enrich ./raw-articles --force --limit 10
```

The default database is `data/app.db`; override it with `--db PATH`. The command
imports the original JSON, performs evidence extraction with `gpt-5.6-luna`, then
discovery synthesis with `gpt-5.6-terra`. Unchanged articles are skipped unless
`--force` is supplied.

SQLite is migrated automatically. `current_article_enrichments` exposes the active
analysis and tags; `enrichment_runs` retains history, and `llm_calls` records request
IDs, failures, latency, token usage, pricing rates, and estimated cost.

Run the offline test suite with:

```bash
poetry run python -m unittest discover -s tests
```
