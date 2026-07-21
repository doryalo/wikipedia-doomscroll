# Live API Raw-Article Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist every validated live API result atomically into the backend watcher directory before responding with success.

**Architecture:** The shared `hydrate` path serializes its Pydantic envelope to a unique same-directory temporary file and atomically publishes it into `backend/data/raw-articles/`. Routes return `{"status": "stored"}` only after that handoff succeeds.

**Tech Stack:** Python, FastAPI, Pydantic v2, standard-library atomic filesystem operations.

---

### Task 1: Add atomic raw-article persistence

**Files:**
- Modify: `wikimedia_api/main.py`
- Test: `/private/tmp/test_live_wikimedia_api.py`

- [ ] Write a failing test that patches the raw-article destination, invokes the persistence helper, and asserts a unique `.json` file parses as `PageResultsDataset`.
- [ ] Run `PYTHONPATH=. .venv-wikimedia-api/bin/python -m unittest discover -s /private/tmp -p 'test_live_wikimedia_api.py' -v` and observe failure because the helper does not exist.
- [ ] Add the persistence helper using `tempfile.NamedTemporaryFile` in the target directory and `os.replace`, then call it after `PageResultsDataset.model_validate` succeeds.
- [ ] Re-run the focused test and expect PASS.

### Task 2: Replace route payloads with handoff acknowledgements

**Files:**
- Modify: `wikimedia_api/main.py`
- Test: `/private/tmp/test_live_wikimedia_api.py`

- [ ] Write a failing OpenAPI assertion that a representative route has the minimal status response model.
- [ ] Change every route to persist its result and return `{"status": "stored"}` only after writing succeeds; map write failures to `500`.
- [ ] Run focused tests, `py_compile`, and OpenAPI checks.

### Task 3: Generate and validate historical-content handoffs

**Files:**
- Create: `backend/data/raw-articles/*.json` (50 generated handoff files)

- [ ] Run a bounded script that hydrates 50 historical article titles through the shared persistence helper.
- [ ] Validate every generated file in `backend/data/raw-articles/` with `PageResultsDataset.model_validate_json` and report count, names, and schema failures.
