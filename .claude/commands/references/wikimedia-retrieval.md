# Wikimedia retrieval reference

Current verification date: 2026-07-21.

This is a production reference for Wikipedia Doomscroll. It intentionally favors official Wikimedia sources and current per-wiki API help. Reverify all quotas, beta endpoints, and deprecations before shipping.

## Contents

1. API families
2. Keys, identity, and rate limits
3. Discovery endpoints
4. Search endpoints
5. Page-card hydration
6. Full content and history
7. Wikidata and semantic enrichment
8. Commons media and attribution
9. Pagination, caching, retries, and CORS
10. Feed architecture
11. Deprecations and unstable surfaces
12. Where to verify and search next

## 1. API families

| Surface | Base | Best use |
|---|---|---|
| MediaWiki Action API | `https://{lang}.wikipedia.org/w/api.php` | Rich queries, generators, page properties, recent changes, random, geo, categories, revisions |
| MediaWiki REST API | `https://{lang}.wikipedia.org/w/rest.php/v1` | Simple search, page metadata/HTML, history, language/media links |
| Wikimedia REST API | `https://{lang}.wikipedia.org/api/rest_v1` | Cached summary/feed/analytics compatibility routes; isolate behind adapters |
| Analytics API | `https://wikimedia.org/api/rest_v1/metrics` | Pageviews, most-viewed pages, edit statistics |
| EventStreams | `https://stream.wikimedia.org/v2/stream` | Live page creation, revisions, recent changes |
| Wikidata Action API | `https://www.wikidata.org/w/api.php` | Entity search and entity retrieval |
| Wikibase REST API | `https://www.wikidata.org/w/rest.php/wikibase/v1` | Modern item/property/statement retrieval |
| Commons Action API | `https://commons.wikimedia.org/w/api.php` | Original files, thumbnails, authors, licenses, structured media data |
| Wikimedia Enterprise | `https://api.enterprise.wikimedia.com/v2` | Authenticated on-demand, structured, snapshot, and paid realtime access |

The API Portal wiki at `api.wikimedia.org` was sunset in June 2026. Documentation now lives on mediawiki.org and in each wiki's `Special:RestSandbox`. Do not confuse the documentation portal sunset with immediate removal of every API route previously documented there.

## 2. Keys, identity, and rate limits

### Do public reads need a key?

No. Normal public reads from Wikipedia, Wikimedia Commons, Wikidata, Analytics, and EventStreams do not require an API key. Send a compliant identifying User-Agent anyway.

Use credentials when:

- editing, uploading, watching, or accessing protected user data: Wikimedia login/OAuth plus appropriate rights;
- needing an authenticated global rate class: OAuth/session behavior must match current rate-limit guidance;
- using Wikimedia Enterprise: account plus bearer token, including free On-demand and Snapshot tiers;
- using a separately documented service whose access policy explicitly requires a token.

Never manufacture accounts or distribute calls across IPs/user agents to evade limits.

### Current global request classes

The official July 2026 overview describes per-minute limits across Action and REST APIs:

| Identity class | Requests/minute |
|---|---:|
| Unidentified automation, IP only | 10 |
| Anonymous browser traffic | 200 |
| Compliant User-Agent only | 200 |
| New/few-edit authenticated user | 200 |
| Established authenticated editor | 2,000 |
| Bot-flagged accounts, certain global-right users, compliant WMCS traffic | Exempt from this global request limit |

Exempt does not mean unlimited: operational limits, endpoint-specific limits, and robot policy still apply. The limits were introduced in 2026 and may change. Look them up rather than encoding them into product behavior.

Operational requirements:

- keep concurrency at three requests or fewer;
- obey `429 Too Many Requests`, `503 Service Unavailable`, and `Retry-After`;
- if no `Retry-After` exists, wait at least five seconds and use exponential backoff;
- use a meaningful User-Agent with app/version and monitored contact information;
- use `Api-User-Agent` where browser JavaScript cannot set `User-Agent`.

Project configuration example:

```text
WIKIMEDIA_CONTACT=https://example.com/contact; ops@example.com
User-Agent=WikipediaDoomscroll/0.1 (+https://example.com/contact; ops@example.com) httpx/0.x
```

`WIKIMEDIA_CONTACT` is this project's configuration name. Wikimedia identifies the client through `User-Agent` or `Api-User-Agent`; it does not issue a public-read API key named `WIKIMEDIA_CONTACT`.

### Enterprise free access

As of June/July 2026, the advertised free tier includes 50,000 On-demand requests/month and 30 Snapshot requests/month or up to 1,500 Snapshot chunks/month. Free snapshots refresh monthly. Enterprise Realtime/firehose access is not part of ordinary unauthenticated public API access and may require a paid arrangement.

## 3. Discovery endpoints

All examples use English Wikipedia. Substitute the correct wiki host and retain it as part of page identity.

### New pages: pollable and hydratable

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&list=recentchanges&rctype=new&rcnamespace=0&rcshow=!redirect&rclimit=50&rcprop=title|ids|timestamp|sizes|flags&maxlag=5
```

Important parameters:

- `rctype=new`: creations only;
- `rcnamespace=0`: encyclopedia articles only;
- `rcshow=!redirect`: exclude redirect creations;
- `rcdir=newer|older`, `rcstart`, `rcend`: deterministic window traversal;
- `rccontinue`: returned continuation token;
- maximum normal limit is usually 500.

Use the generator form to get usable cards without a second request:

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&generator=recentchanges&grctype=new&grcnamespace=0&grcshow=!redirect&grclimit=20&prop=extracts|pageimages|pageterms|info|pageprops&exintro=1&explaintext=1&exchars=500&piprop=thumbnail|original&pithumbsize=640&wbptterms=description&inprop=url&maxlag=5
```

RecentChanges retention is finite. It is not a permanent creation-date database. For historical creation time, retrieve the oldest revision or use bulk/analytics datasets.

### New pages and edits: live stream

```text
https://stream.wikimedia.org/v2/stream/page-create
https://stream.wikimedia.org/v2/stream/recentchange
https://stream.wikimedia.org/v2/stream/revision-create
```

EventStreams uses Server-Sent Events. For `recentchange`, filter client-side for:

```text
server_name == "en.wikipedia.org"
namespace == 0
type == "new" or type == "edit"
meta.domain != "canary"
```

There is no general server-side wiki filter. Public history is limited, typically about 7–31 days depending on stream configuration. Use `since=` sparingly, persist event IDs, reconnect after the infrastructure's roughly 15-minute connection termination, and resume using `Last-Event-ID`.

Use EventStreams as a signal source, not the direct frontend feed. Queue, deduplicate, filter, hydrate, and rank events before serving them.

### Random pages

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&generator=random&grnnamespace=0&grnfilterredir=nonredirects&grnminsize=1000&grnlimit=20&prop=extracts|pageimages|pageterms|info&exintro=1&explaintext=1&exchars=500&pithumbsize=640&wbptterms=description&inprop=url
```

Random results are a fixed sequence from a random starting point, not independent perfect samples. Apply local deduplication, diversity, minimum-quality filters, and recently-served suppression.

### Most-viewed pages

Daily top articles:

```http
GET https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia.org/all-access/2026/07/20
```

Monthly top list:

```http
GET https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia.org/all-access/2026/07/all-days
```

Top results can include `Main_Page`, special pages, non-content titles, and news spikes. Normalize titles, resolve pages through Action API, discard non-mainspace/missing/redirect-only entries, and hydrate the remaining page IDs in a batch.

Analytics is aggregated and delayed. It is not a real-time trending stream. A better trending signal combines the last complete top-pageview data with recent edit velocity and local engagement.

### Category discovery

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&generator=categorymembers&gcmtitle=Category:Physics&gcmnamespace=0&gcmtype=page&gcmlimit=50&prop=extracts|pageimages|pageterms&exintro=1&explaintext=1&pithumbsize=640&wbptterms=description
```

Follow `gcmcontinue`. Category trees may contain cycles and maintenance categories; bound traversal depth and maintain a visited set.

### Nearby/geospatial discovery

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&generator=geosearch&ggscoord=31.778|35.235&ggsradius=10000&ggsnamespace=0&ggslimit=50&prop=coordinates|extracts|pageimages|pageterms&exintro=1&explaintext=1&pithumbsize=640&wbptterms=description
```

`geosearch` requires the GeoData extension, available on Wikipedia. It returns distance ordering and supports continuation. Location is sensitive user data: do not persist precise user coordinates unnecessarily.

### Featured and on-this-day content

Compatibility routes include:

```text
GET https://en.wikipedia.org/api/rest_v1/feed/featured/2026/07/21
GET https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/07/21
```

Support varies by language. Featured is documented as unstable and on-this-day as experimental. Put them behind an optional adapter with schema validation, timeouts, cached last-known-good content, and a kill switch.

## 4. Search endpoints

### Full-text search with Action API

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&list=search&srsearch=quantum%20gravity&srnamespace=0&srlimit=20&srprop=size|wordcount|timestamp|snippet
```

Useful controls:

- `sroffset`/`continue`: pagination;
- `srsort=relevance`: normal search;
- `srsort=create_timestamp_desc`: newest matching pages;
- `srsort=last_edit_desc`: recently edited matches;
- `srsort=incoming_links_desc`: crude authority ordering;
- `srsort=random` or `user_random`: discovery sampling;
- `srinfo=suggestion`: spelling/query suggestion;
- CirrusSearch operators such as `incategory:`, `intitle:`, `haswbstatement:`, and `morelike:`.

Search snippets contain highlighted HTML and are not article summaries. Sanitize them or request plain extracts through a generator.

### Search and hydrate in one request

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&generator=search&gsrsearch=quantum%20gravity&gsrnamespace=0&gsrlimit=20&prop=extracts|pageimages|pageterms|info|pageprops&exintro=1&explaintext=1&exchars=500&piprop=thumbnail|original&pithumbsize=640&wbptterms=description&inprop=url
```

Each generated page includes an `index`; preserve it to maintain search rank.

### Related articles

The old `/api/rest_v1/page/related/{title}` endpoint was decommissioned and returns 403. Use CirrusSearch:

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&generator=search&gsrsearch=morelike:Marie_Curie&gsrnamespace=0&gsrlimit=20&prop=extracts|pageimages|pageterms|info&exintro=1&explaintext=1&exchars=500&pithumbsize=640&wbptterms=description
```

`morelike:` is greedy and cannot be combined freely with other search terms. `morelikethis:` supports additional filters on Wikimedia's CirrusSearch deployment. Treat this as search behavior, not a guaranteed stable recommendation contract; wrap and test it.

### Prefix/typeahead search

Core REST:

```http
GET https://en.wikipedia.org/w/rest.php/v1/search/title?q=solar&limit=10
```

Action API with richer hydration:

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&generator=prefixsearch&gpssearch=Albert%20Ei&gpsnamespace=0&gpslimit=10&prop=pageimages|pageterms|info&piprop=thumbnail&pithumbsize=80&wbptterms=description&inprop=url
```

Core REST also exposes `/search/page?q=...&limit=...` for simple full-text results. Action API is preferable when several page properties must be joined into each result.

## 5. Page-card hydration

A feed card normally needs:

- `wiki`, `pageid`, normalized title, canonical URL;
- current revision ID/timestamp;
- intro extract;
- representative thumbnail and dimensions;
- Wikidata short description and QID when available;
- discovery reason and local ranking metadata;
- article license/provenance fields.

Preferred approach: generate candidates and fetch page properties in the same Action API request, or batch known page IDs/titles:

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&pageids=9228|736|18618509&redirects=1&prop=extracts|pageimages|pageterms|info|pageprops|revisions&exintro=1&explaintext=1&exchars=500&piprop=thumbnail|original&pithumbsize=640&wbptterms=description&inprop=url&rvprop=ids|timestamp
```

Normal clients can request up to 50 titles/page IDs per query; `apihighlimits` clients can often request up to 500. Individual property modules can impose tighter limits.

The Wikimedia REST summary route remains convenient and cache-friendly:

```http
GET https://en.wikipedia.org/api/rest_v1/page/summary/Earth
```

Use it for isolated lookups or compatibility, not as an N+1 card hydrator. Keep it behind an adapter because the underlying RESTBase architecture is being retired and endpoint ownership is migrating.

## 6. Full content and history

### Core REST page resources

```text
GET /w/rest.php/v1/page/Earth/bare
GET /w/rest.php/v1/page/Earth/with_html
GET /w/rest.php/v1/page/Earth/html
GET /w/rest.php/v1/page/Earth/history
GET /w/rest.php/v1/page/Earth/links/language
GET /w/rest.php/v1/page/Earth/links/media
```

- `bare`: page identity, latest revision, content model, license, HTML URL;
- `with_html`: metadata plus current HTML in JSON;
- `html`: HTML representation directly;
- `history`: revision summaries with `older`/`newer` API URLs;
- language/media link routes: bounded linked resources.

Encode title path segments correctly; a `/` in a subpage title must be percent-encoded as `%2F`. Follow `301` title-normalization redirects deliberately and persist the canonical title.

### Wikitext and revision data

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&titles=Earth&prop=revisions&rvslots=main&rvprop=ids|timestamp|user|userid|comment|size|sha1|content&rvlimit=1
```

With `formatversion=2`, content is under the main slot. Request `content` only when needed; it is substantially larger than metadata.

History pagination:

```http
GET https://en.wikipedia.org/w/api.php?action=query&format=json&formatversion=2&titles=Earth&prop=revisions&rvprop=ids|timestamp|user|comment|size&rvlimit=50&rvdir=older
```

Round-trip `rvcontinue`. Deleted/suppressed fields can be absent or represented by hidden markers; schemas must allow this.

### Parsed sections and HTML

Action parse can return full or individual-section HTML plus sections, links, categories, images, templates, and warnings:

```http
GET https://en.wikipedia.org/w/api.php?action=parse&format=json&formatversion=2&page=Earth&prop=text|sections|displaytitle|langlinks|categories|links|images&parser=parsoid
```

For a specific section, add `section={index}`. For production display, prefer Parsoid/Core REST HTML rather than attempting to interpret wikitext in the application.

The former mobile-sections endpoint is not a durable dependency. If structured, pre-parsed sections are essential at large scale, evaluate Wikimedia Enterprise Structured Contents.

### Other page properties

Action API supports combinations of:

- `categories`, `links`, `extlinks`, `images`, `templates`;
- `langlinks`, `coordinates`, `contributors`;
- `pageprops` including `wikibase_item` and disambiguation markers;
- `revisions`, redirects, backlinks (`linkshere`), and transclusions.

Every list-like property has its own limit/continuation key. A response can include multiple continuation fields at once; return all of them unchanged.

## 7. Wikidata and semantic enrichment

Resolve a Wikipedia page directly to its entity:

```http
GET https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&sites=enwiki&titles=Earth&props=info|labels|descriptions|claims|sitelinks&languages=en&languagefallback=1
```

Or use the article's `pageprops.wikibase_item` QID and request by ID:

```http
GET https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&ids=Q2&props=labels|descriptions|claims|sitelinks&languages=en&languagefallback=1
```

Use `wbsearchentities` for entity search, not for ordinary Wikipedia article search.

The modern Wikibase REST base is:

```text
https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/Q2
```

Use direct entity APIs when QIDs are known. Use the Wikidata Query Service/SPARQL for scoped analytical graph queries, not synchronous per-card lookups: query complexity, timeouts, and service load make it a poor critical-path dependency.

Useful claims for local ranking/filtering can include P31 (instance of), P279 (subclass), P625 (coordinates), P18 (image), and dates. Do not assume every claim exists or is singular. Respect ranks, qualifiers, references, calendar models, and units when correctness matters.

Wikidata structured data is CC0, while linked Wikipedia text and Commons files retain their own licenses.

## 8. Commons media and attribution

PageImages returns a representative image heuristic. Resolve its `File:` title against Commons for actual reuse data:

```http
GET https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2&titles=File:Example.jpg&prop=imageinfo&iiprop=url|size|mime|sha1|timestamp|user|extmetadata&iiurlwidth=1280&iiextmetadatalanguage=en&iiextmetadatafilter=Artist|Credit|LicenseShortName|LicenseUrl|UsageTerms|AttributionRequired|Copyrighted|ImageDescription
```

Important fields:

- original `url`, description URL, thumbnail URL and dimensions;
- file SHA-1/timestamp for cache identity;
- `Artist`, `Credit`, `LicenseShortName`, `LicenseUrl`, `UsageTerms`;
- public-domain/copyright and attribution indicators when supplied.

`extmetadata` is expensive and HTML-formatted. Request only required keys, limit batch size, sanitize displayed values, and cache by file revision/hash. Verify whether a file is local to a Wikipedia or hosted on Commons; the attribution source host must match the actual file.

Commons media can have CC BY, CC BY-SA, public-domain, GFDL, or other licenses and non-copyright restrictions. Never infer the image license from the article license.

## 9. Pagination, caching, retries, and CORS

### Action API continuation

If a response includes:

```json
{
  "continue": {
    "rccontinue": "20260721120000|1234567890",
    "continue": "-||"
  }
}
```

send every returned key/value with the next identical query. Do not parse, increment, shorten, or combine continuation values. Generators and properties can return several tokens together.

### REST pagination

Core REST history responses provide `older`, `newer`, or other route URLs. Treat them as opaque and allowlist the Wikimedia host/path before following server-provided URLs.

### Conditional requests

Store an upstream `ETag`, then send:

```http
If-None-Match: W/"917562775"
```

On `304 Not Modified`, reuse the cached body and update validation time. Do not attempt to decode semantic meaning from an ETag.

Recommended local policy, not a Wikimedia guarantee:

| Data | Starting policy |
|---|---|
| Live/new candidate pools | 30–60 seconds |
| Search/related candidates | 2–10 minutes |
| Daily top pageviews | Through next data refresh, recheck hourly |
| Page card by current revision | 15–60 minutes plus ETag revalidation |
| HTML/wikitext by immutable revision | Days to effectively immutable |
| Wikidata entity | 1–24 hours plus ETag/revision awareness |
| Commons license metadata by file SHA-1 | Long-lived; revalidate periodically |
| Featured/on-this-day | Cache until date boundary; keep last-known-good |

Use bounded Redis storage, TTL jitter, request coalescing/singleflight, stale-while-revalidate, and stale-if-error for non-safety-critical content.

### Retry matrix

| Condition | Behavior |
|---|---|
| `429` | Honor `Retry-After`; reduce request rate |
| `503` or `maxlag` | Honor delay and retry with bounded jitter |
| Timeout/connect reset | Retry safe GET a small bounded number of times |
| `301` title normalization | Follow intentionally; save canonical title |
| `404` | Negative-cache briefly; do not loop |
| `403` deprecated/forbidden route | Do not retry; migrate or disable adapter |
| JSON/schema mismatch | Quarantine response, serve fallback, alert |

For non-interactive Action API jobs, `maxlag=5` is a considerate default. A maxlag response can be HTTP 200 with an API error body depending on the path/client; inspect structured error codes, not only HTTP status.

### CORS

Unauthenticated Action API browser calls commonly use `origin=*`. Authenticated CORS requires the expected origin and credential behavior. Prefer backend calls so identification, secrets, rate limiting, schemas, and caching are controlled centrally.

## 10. Feed architecture

Do not retrieve a fresh page from Wikimedia for every swipe. Build inventory ahead of demand.

```text
Discovery adapters
    -> candidate queue
    -> identity normalization and dedupe
    -> batched card hydration
    -> local eligibility and ranking
    -> Redis/PostgreSQL feed inventory
    -> opaque application cursor
    -> frontend prefetch window

Card open
    -> revision-aware HTML cache
    -> optional Wikidata enrichment
    -> Commons attribution cache
```

Candidate sources should degrade independently. A practical mix:

- 25% interest/related (`morelike:` plus local user model);
- 20% current/popular (Analytics plus edit velocity);
- 20% random/serendipity;
- 15% new-page exploration after quality delay/filtering;
- 10% category/nearby when relevant;
- 10% curated/featured.

Those percentages are product hypotheses, not Wikimedia requirements. Experiment locally without increasing upstream traffic: candidate generation and hydration should be shared across users, while personalization happens against cached inventory.

Use a quality delay for new articles so deletion, redirect conversion, and obvious spam patrol can settle. Possible local signals include minimum size, lead image presence, non-disambiguation, Wikidata linkage, reference/link density, survival time, pageview/edit activity, and user feedback. Do not present these as Wikimedia quality judgments.

## 11. Deprecations and unstable surfaces

- RESTBase technology is being retired. Some `/api/rest_v1` routes remain operational or have been rerouted, but new integrations should prefer Action API or Core REST where equivalent.
- `/api/rest_v1/page/related/{title}` was blocked/decommissioned in 2025. Use Action API CirrusSearch `morelike:`.
- Do not depend on mobile-sections. Prefer Core REST/Parsoid HTML, Action parse, or Enterprise Structured Contents.
- Trailing-slash transform routes were removed in January 2026; use documented non-trailing-slash routes.
- The API Portal was sunset in June 2026. Use mediawiki.org and `Special:RestSandbox`.
- Link Recommendation API is for editor link-placement suggestions, not reader article recommendations, and was scheduled for gradual deprecation beginning July 2026.
- Attribution API is beta in 2026. Its results can be incomplete; reusers remain responsible for license compliance.
- Wikifeeds featured/on-this-day endpoints have unstable/experimental status and language-specific coverage.
- Action API JSON remains the supported default. Do not use removed/deprecated PHP or XSLT output formats.

Check response `Deprecation` headers and the official API changelog during implementation and routine maintenance.

## 12. Where to verify and search next

Use these sources in this order:

1. Per-wiki generated Action API help, because it reflects installed extensions and parameters:
   - `https://en.wikipedia.org/w/api.php?action=help&modules=query%2Brecentchanges`
   - replace the module name for `search`, `random`, `geosearch`, `imageinfo`, and others.
2. Per-wiki interactive REST Sandbox:
   - `https://en.wikipedia.org/wiki/Special:RestSandbox`
3. Wikimedia API catalog:
   - `https://www.mediawiki.org/wiki/API:Web_APIs_hub/API_index`
4. MediaWiki REST reference:
   - `https://www.mediawiki.org/wiki/API:REST_API/Reference`
5. Action API search/discovery and query docs:
   - `https://www.mediawiki.org/wiki/API:Search_and_discovery`
   - `https://www.mediawiki.org/wiki/API:Query`
6. Current global rate limits and etiquette:
   - `https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits`
   - `https://www.mediawiki.org/wiki/API:Etiquette`
7. API changelog and deprecation policy:
   - `https://www.mediawiki.org/wiki/Wikimedia_APIs/Changelog`
   - `https://www.mediawiki.org/wiki/API/Deprecation`
8. EventStreams docs and live stream specification:
   - `https://wikitech.wikimedia.org/wiki/EventStreams`
   - `https://stream.wikimedia.org/?doc`
9. Analytics reference:
   - `https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/`
10. Wikidata access and Wikibase REST docs:
    - `https://www.wikidata.org/wiki/Wikidata:Data_access`
    - `https://www.wikidata.org/wiki/Wikidata:REST_API`
11. Commons media APIs:
    - `https://commons.wikimedia.org/wiki/Commons:API/MediaWiki`
    - `https://www.mediawiki.org/wiki/API:Imageinfo`
12. Content reuse and attribution:
    - `https://www.mediawiki.org/wiki/Wikimedia_APIs/Content_reuse`
    - `https://www.mediawiki.org/wiki/Attribution_API`
13. Bulk/high-volume access:
    - `https://enterprise.wikimedia.com/docs/`
    - `https://meta.wikimedia.org/wiki/Data_dumps/Dump_format`

When an endpoint is unclear, search the official domains with the exact route or Action module name. Prefer generated help, OpenAPI/REST Sandbox, and current changelogs over tutorials. Verify live response schemas with a compliant User-Agent and a low-volume request before freezing typed models.
