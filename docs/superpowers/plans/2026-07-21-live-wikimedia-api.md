# Live Wikimedia API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-file FastAPI adapter that fetches live Wikimedia discovery data and returns the shared page-results envelope.

**Architecture:** `wikimedia_api/main.py` owns route definitions, lifespan-managed HTTP access, upstream rate coordination, discovery adapters, category round-robin selection, and shared card/content hydration. It imports the existing Pydantic response models from `wikimedia_content.models`; it does not reuse the executable notebook or write snapshots.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, httpx, unittest mock transport.

---

### Task 1: Define the public FastAPI contract and singleton HTTP lifecycle

**Files:**
- Create: `wikimedia_api/main.py`
- Test: `/private/tmp/test_live_wikimedia_api.py`

- [ ] **Step 1: Write the failing lifecycle and schema-response test**

```python
from wikimedia_api.main import app

def test_openapi_exposes_live_routes():
    paths = app.openapi()["paths"]
    assert "/v1/random" in paths
    assert "/v1/categories" in paths
    assert "/v1/content/full-text" in paths
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest discover -s /private/tmp -p 'test_live_wikimedia_api.py' -v`

Expected: failure because `wikimedia_api.main` does not exist.

- [ ] **Step 3: Implement the application shell**

Create a FastAPI app with a lifespan-managed `httpx.AsyncClient`, a compliant
User-Agent derived from `WIKIMEDIA_CONTACT`, Wikimedia-host validation, Action
API `maxlag=5`, explicit timeouts, and a process-wide 200/minute + three-call
concurrency coordinator. Convert upstream retryable failures to `503` and
invalid upstream payloads to `502`.

- [ ] **Step 4: Run the lifecycle and OpenAPI test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest discover -s /private/tmp -p 'test_live_wikimedia_api.py' -v`

Expected: PASS.

### Task 2: Implement discovery adapters and common hydration

**Files:**
- Create: `wikimedia_api/main.py`
- Test: `/private/tmp/test_live_wikimedia_api.py`

- [ ] **Step 1: Write the failing category round-robin test**

```python
from wikimedia_api.main import round_robin_category_articles

def test_category_round_robin_stops_at_requested_count():
    selections = round_robin_category_articles(
        {"A": ["A1", "A2"], "B": ["B1", "B2"], "C": ["C1"]}, count=4
    )
    assert selections == [("A", "A1"), ("B", "B1"), ("C", "C1"), ("A", "A2")]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest discover -s /private/tmp -p 'test_live_wikimedia_api.py' -v`

Expected: failure because `round_robin_category_articles` does not exist.

- [ ] **Step 3: Implement ordered discovery and hydration**

Implement async adapters for random, daily/monthly/yearly views, category name,
category index, members, subcategories, nearby, featured, on-this-day,
full-text and hydrated search, related, Action/Core prefix, page-card, and the
five content variants. Batch card metadata, retrieve one no-image plain-text
extract per accepted page, then construct `PageResultsDataset` with sequential
ranks and explicit shortfall metadata.

- [ ] **Step 4: Run the adapter tests to verify they pass**

Run: `PYTHONPATH=. python3 -m unittest discover -s /private/tmp -p 'test_live_wikimedia_api.py' -v`

Expected: PASS.

### Task 3: Expose all tutorial routes with minimal controls

**Files:**
- Create: `wikimedia_api/main.py`
- Test: `/private/tmp/test_live_wikimedia_api.py`

- [ ] **Step 1: Write the failing parameter-contract test**

```python
from wikimedia_api.main import app

def test_single_page_content_route_has_no_count_parameter():
    parameters = app.openapi()["paths"]["/v1/content/full-text"]["get"]["parameters"]
    assert [parameter["name"] for parameter in parameters] == ["title"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest discover -s /private/tmp -p 'test_live_wikimedia_api.py' -v`

Expected: failure because the route is absent or has the wrong parameters.

- [ ] **Step 3: Register routes and response models**

Register `/v1/random`, `/v1/most-viewed/day`, `/v1/most-viewed/month`,
`/v1/most-viewed/year`, category routes, `/v1/nearby`, `/v1/featured`,
`/v1/on-this-day`, search/related/prefix routes, `/v1/page-card`, and the
five `/v1/content/...` routes. Collection routes accept only relevant inputs
plus bounded `count`; single-page routes accept only `title`. Every route uses
`response_model=PageResultsDataset`.

- [ ] **Step 4: Run all focused checks**

Run: `PYTHONPATH=. python3 -m unittest discover -s /private/tmp -p 'test_live_wikimedia_api.py' -v && python3 -m py_compile wikimedia_api/main.py && python3 -c 'from wikimedia_api.main import app; print(len(app.openapi()["paths"]))'`

Expected: tests pass, compile succeeds, and OpenAPI prints the registered route count.

- [ ] **Step 5: Commit implementation**

```bash
git add wikimedia_api/main.py docs/superpowers/plans/2026-07-21-live-wikimedia-api.md
git commit -m "feat: add live Wikimedia FastAPI adapter"
```
