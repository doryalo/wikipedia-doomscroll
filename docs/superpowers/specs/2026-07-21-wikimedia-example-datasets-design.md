# Wikimedia Example Datasets Design

## Objective

Create actual Wikimedia content datasets for every retrieval example in
`wikimedia_retrieval_tutorial.py`. Store every dataset and its shared JSON
Schema in one `wikimedia_content/` directory. Each dataset should contain ten
article pages when Wikimedia provides enough valid results.

## Shared File Contract

`wikimedia_content/page-results.schema.json` defines one envelope used by every
dataset file. The envelope contains:

- schema version, example identifier, description, retrieval timestamp, wiki,
  upstream endpoint, and original parameters;
- expansion metadata explaining whether results were natural or expanded;
- result count and an ordered `pages` array;
- per-page rank and source-specific discovery metadata;
- page ID, normalized title, canonical URL, revision ID/timestamp, description,
  Wikidata ID, byte length, touched timestamp, and disambiguation status;
- the complete current article as plain text.

The shared page object contains no thumbnail, original-image, or other image
fields. Unknown optional values are represented as `null`, not omitted.

## Dataset Mapping

Natural page-list examples retain their native ordering and take the first ten
valid namespace-zero pages: random, daily/monthly/yearly most-viewed, category
members, nearby, full-text search, hydrated search, related search, both prefix
search variants, featured, and on-this-day.

Examples without ten native article pages expand deterministically:

- category-name and all-category examples resolve their first matching
  categories, then gather article members in category/result order;
- subcategory discovery gathers article members from returned subcategories;
- the three-title card example retains its explicit titles and fills remaining
  positions with `morelike:Genghis_Khan` results;
- intro, complete-text, parsed-section, rendered-HTML, and other-properties
  examples retain `Genghis Khan` first and fill remaining positions with
  `morelike:Genghis_Khan` results.

Expansion removes duplicates by `(wiki, page_id)`, excludes missing pages,
redirect-only results, non-mainspace pages, and disambiguation pages, and stops
at ten results.

## Retrieval Flow

For each example:

1. Retrieve its candidate titles in the same way demonstrated by the tutorial.
2. Apply the deterministic expansion rule if fewer than ten candidates exist.
3. Hydrate card metadata for the candidate pool in one Action API query using
   `pageterms|info|pageprops|revisions`, URL metadata, Wikidata descriptions,
   and current revision identity.
4. Fetch each eligible page's complete plain-text extract individually because
   Wikimedia limits full-article `prop=extracts` requests to one page. Cache
   extracts by normalized title across datasets.
5. Restore candidate ordering, attach source-specific discovery metadata, and
   write the shared envelope atomically.

Requests use the tutorial's compliant identifying User-Agent, remain
sequential, send `maxlag=5`, and honor Wikimedia errors. No HTML scraping or
image retrieval is used.

## Generation and Reproducibility

The tutorial file remains the executable generator so credentials and request
policy stay centralized. A generation flag writes all datasets into
`wikimedia_content/`. Date-sensitive examples record their exact date in source
parameters and output metadata. Random results are snapshots and therefore not
reproducible across runs; their retrieval timestamp and revision IDs preserve
snapshot identity.

## Validation

After generation:

- validate every dataset against `page-results.schema.json`;
- require exactly ten pages unless the file records an explicit upstream
  shortfall;
- require non-empty full text and canonical identity for every page;
- assert image fields are absent;
- assert page IDs are unique within each file;
- parse every JSON file and run Python syntax verification on the generator.
