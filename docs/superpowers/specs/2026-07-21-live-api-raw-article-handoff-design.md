# Live API Raw-Article Handoff Design

## Goal

Change the live Wikimedia API so every successful endpoint run atomically hands
its validated page-results envelope to the backend's watched raw-article input
directory, then returns a minimal successful response.

## Backend contract

`backend/app/enrichment_watcher.py` watches `backend/data/raw-articles/` for
direct `.json` files. The enrichment loader accepts the shared page-results
envelope and extracts each page's identity, canonical URL, and full plain-text
content. The watcher processes files asynchronously after they appear.

## API behavior

The shared hydration path remains responsible for live Wikimedia retrieval and
Pydantic validation. It then serializes exactly one `PageResultsDataset` per
request to a new file named `{example_id}-{UTC timestamp}-{uuid}.json` in
`backend/data/raw-articles/`.

The write is atomic: create a same-directory temporary file whose suffix is not
`.json`, flush it, then publish it with `os.replace()`. This prevents the
watcher from parsing a partially written envelope. The API returns `200` with
`{"status": "stored"}` only after the final file has been published. Any
write failure produces `500` and no success body.

The response confirms retrieval, schema validation, and durable handoff only.
It does not wait for or claim downstream enrichment/post creation, because the
existing watcher performs that work asynchronously.

## Scope

Modify only `wikimedia_api/main.py` and add a focused temporary test. Do not
change the backend watcher, database, enrichment pipeline, or JSON schema.
