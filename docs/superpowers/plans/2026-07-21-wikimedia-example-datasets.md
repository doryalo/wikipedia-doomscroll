# Wikimedia Example Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate schema-valid JSON snapshots containing ten fully hydrated Wikipedia articles for every article-related example in `wikimedia_retrieval_tutorial.py`.

**Architecture:** Extend the existing notebook-style tutorial with pure candidate, hydration, envelope, and validation helpers. Generate 22 self-contained dataset files under `wikimedia_content/`, all governed by one strict JSON Schema and using complete plain-text article extracts without image fields.

**Tech Stack:** Python 3.11+, `httpx`, standard-library JSON/datetime/pathlib, Wikimedia Action/Core REST/Analytics/Wikifeeds APIs, JSON Schema Draft 2020-12.

---

## File Structure

- Modify `wikimedia_retrieval_tutorial.py`: candidate discovery, deterministic expansion, batch hydration, dataset writing, and validation.
- Create `wikimedia_content/page-results.schema.json`: shared Draft 2020-12 contract.
- Create 22 `wikimedia_content/*.json` snapshots: one per retrieval/content example.

The dataset filenames are:

```text
random-pages.json
most-viewed-day.json
most-viewed-month.json
most-viewed-year.json
category-name-search.json
all-categories.json
category-members.json
category-subcategories.json
nearby-jerusalem.json
featured.json
on-this-day.json
full-text-search.json
hydrated-search.json
related-genghis-khan.json
prefix-action.json
prefix-core-rest.json
page-card-hydration.json
content-intro.json
content-full-text.json
content-section.json
content-html.json
other-page-properties.json
```

### Task 1: Shared schema and pure envelope contract

**Files:**
- Modify: `wikimedia_retrieval_tutorial.py`
- Create: `wikimedia_content/page-results.schema.json`

- [ ] **Step 1: Run a failing contract assertion**

Use an AST definitions-only loader and assert that `dataset_schema()` and
`make_dataset_envelope()` exist, that `pages` requires exactly ten items unless
`expansion.shortfall` is true, and that no page property contains `image`,
`thumbnail`, or `original_image`.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -c 'import wikimedia_retrieval_tutorial as t; t.dataset_schema()'
```

Expected: failure because `dataset_schema` does not exist.

- [ ] **Step 3: Implement the contract**

Add `dataset_schema()`, `make_dataset_envelope(...)`, `validate_dataset(...)`,
and `write_json_atomic(...)`. The schema requires source metadata, expansion
metadata, result count, and ordered page objects with identity, card, discovery,
and `content.full_plain_text` fields. Set `additionalProperties: false` at every
known object boundary and omit all image fields.

- [ ] **Step 4: Verify GREEN**

Run the definitions-only assertion and `python3 -m py_compile
wikimedia_retrieval_tutorial.py`. Expected: both exit zero.

### Task 2: Candidate discovery and deterministic expansion

**Files:**
- Modify: `wikimedia_retrieval_tutorial.py`

- [ ] **Step 1: Run failing pure-function assertions**

Assert that `dedupe_titles(["Earth", "Earth", "Moon"])` returns
`["Earth", "Moon"]`, that `expand_with_related(["Genghis Khan"], related)`
retains the anchor first and returns ten unique titles, and that the static
dataset specification contains exactly the 22 filenames listed above.

- [ ] **Step 2: Verify RED**

Expected: missing-function failures.

- [ ] **Step 3: Implement discovery adapters**

Add candidate collectors for random, daily/monthly/yearly top pages, category
name/all-category/member/subcategory flows, nearby, featured, on-this-day,
full-text/hydrated/related/prefix searches, explicit card titles, and the five
Genghis Khan content/property examples. Preserve native ranks and attach
source-specific metadata such as views, distance, search index, event year, or
category title.

- [ ] **Step 4: Implement expansion**

Use category members for category-derived expansion and
`morelike:Genghis_Khan` for explicit/single-page expansion. Dedupe titles while
preserving order and cap every candidate list at ten.

- [ ] **Step 5: Verify GREEN**

Run the pure-function assertions. Expected: exactly 22 specifications and ten
unique expanded titles in fixtures.

### Task 3: Batch hydration and dataset generation

**Files:**
- Modify: `wikimedia_retrieval_tutorial.py`
- Create: `wikimedia_content/*.json`

- [ ] **Step 1: Run a failing hydration normalization assertion**

Provide a representative Action API payload and assert that
`hydrate_dataset_pages(...)` restores candidate order, includes full untruncated
plain text and revision identity, carries discovery metadata, and excludes
missing/disambiguation/image data.

- [ ] **Step 2: Verify RED**

Expected: missing-function failure.

- [ ] **Step 3: Implement batched metadata plus cached content hydration**

Query candidate card metadata with `prop=pageterms|info|pageprops|revisions`,
`redirects=1`, `inprop=url`, `wbptterms=description`, and
`rvprop=ids|timestamp`. Normalize and restore candidate order after title
normalization/redirects. Fetch each complete plain-text extract separately with
`prop=extracts`, `explaintext=1`, and `exsectionformat=plain`, caching by
normalized title across datasets because Wikimedia limits full extracts to one
page per request.

- [ ] **Step 4: Implement generation entry point**

Add `generate_all_datasets(output_dir=Path("wikimedia_content"))`. It writes
the schema first, then discovers, expands, hydrates, validates, and atomically
writes all 22 datasets. It records UTC retrieval time and explicit shortfall
metadata when fewer than ten eligible articles remain.

- [ ] **Step 5: Generate live snapshots**

Run one identified sequential generation command using the configured
`WIKIMEDIA_CONTACT`. Expected: schema plus 22 dataset files written.

### Task 4: Full validation and handoff

**Files:**
- Modify: `wikimedia_retrieval_tutorial.py`
- Verify: `wikimedia_content/*.json`

- [ ] **Step 1: Validate every artifact**

Parse the schema and each dataset, run `validate_dataset`, require 22 dataset
files, require ten pages unless a shortfall is recorded, require unique page
IDs, non-empty content, canonical URLs and revision IDs, and reject image keys.

- [ ] **Step 2: Verify generator syntax and repository whitespace**

Run:

```bash
python3 -m py_compile wikimedia_retrieval_tutorial.py
git diff --check
```

Expected: both exit zero.

- [ ] **Step 3: Report actual generation totals**

Report dataset count, total page records, files with shortfalls, and validation
result. Do not claim live verification unless generation and validation both
completed successfully.
