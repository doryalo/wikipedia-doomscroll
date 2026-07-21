# %% [markdown]
# # Wikimedia retrieval examples
#
# A single-file, notebook-style tutorial and dataset generator. Open it in VS
# Code, PyCharm, Spyder, or Jupyter with Jupytext support and run one `# %%`
# cell at a time. It can also run as a normal Python script.
#
# Install once:
#
#     python3 -m pip install httpx
#
# Set `WIKIMEDIA_CONTACT` to a monitored email or HTTPS contact URL before a
# live request. It is included in the required identifying User-Agent.
#
# Run interactive examples:
#
#     python3 wikimedia_retrieval_tutorial.py
#
# Regenerate every JSON snapshot in `wikimedia_content/`:
#
#     python3 wikimedia_retrieval_tutorial.py --generate-json
#
# Regenerate only named examples (comma-separated):
#
#     python3 wikimedia_retrieval_tutorial.py \
#       --generate-json-only=random-pages,most-viewed-day,related-genghis-khan
#
# Generation overwrites the selected JSON snapshots. Results are live API
# snapshots, so random, featured, date-based, and popularity results can vary.
# Only official Wikimedia APIs are used; no Wikipedia HTML pages are scraped.
# API facts were checked against the project reference on 2026-07-21.

# %% Configuration and tiny HTTP helpers
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import quote, urlparse

import httpx


RUN_LIVE_EXAMPLES = True
GENERATE_JSON_DATASETS = False
GENERATE_JSON_ONLY: set[str] | None = None
WIKIMEDIA_CONTACT = "krystof.zak@gmail.com"
LANGUAGE = "en"

if "--generate-json" in sys.argv:
    RUN_LIVE_EXAMPLES = False
    GENERATE_JSON_DATASETS = True
for argument in sys.argv:
    if argument.startswith("--generate-json-only="):
        RUN_LIVE_EXAMPLES = False
        GENERATE_JSON_DATASETS = True
        GENERATE_JSON_ONLY = set(argument.split("=", 1)[1].split(","))

ACTION_API = f"https://{LANGUAGE}.wikipedia.org/w/api.php"
CORE_REST = f"https://{LANGUAGE}.wikipedia.org/w/rest.php/v1"

HEADERS = {
    # This header is what qualifies identified server-side reads for Wikimedia's
    # normal anonymous request class. Use a monitored email or HTTPS contact URL.
    "User-Agent": (
        "WikipediaDoomscrollExamples/0.1 "
        f"(+{WIKIMEDIA_CONTACT}) httpx/{httpx.__version__}"
    ),
    "Accept-Encoding": "gzip",
}

client = httpx.Client(headers=HEADERS, timeout=20.0, follow_redirects=True)


def _check_contact() -> None:
    if WIKIMEDIA_CONTACT.startswith("replace-"):
        raise RuntimeError("Replace WIKIMEDIA_CONTACT before making live requests")


def _check_wikimedia_url(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    allowed = ("wikipedia.org", "wikimedia.org", "wikidata.org")
    if not any(host == item or host.endswith(f".{item}") for item in allowed):
        raise ValueError(f"Not an allowed Wikimedia URL: {url}")


def get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Perform one identified, sequential GET and print exactly what was called."""

    _check_contact()
    _check_wikimedia_url(url)
    query = dict(params or {})
    if url == ACTION_API:
        query.setdefault("maxlag", 5)
    print("\nGET", url)
    if query:
        print("params =", json.dumps(query, indent=2, ensure_ascii=False))
    response = client.get(url, params=query)
    if response.status_code in {429, 503}:
        wait = response.headers.get("Retry-After", "at least 5 seconds")
        raise RuntimeError(f"HTTP {response.status_code}; wait {wait}, then retry")
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("error"):
        error = payload["error"]
        if error.get("code") == "maxlag":
            raise RuntimeError(f"Wikimedia maxlag response: {error}")
        raise RuntimeError(
            f"Wikimedia API error {error.get('code')}: {error.get('info')}"
        )
    return payload


def get_html(url: str) -> str:
    _check_contact()
    _check_wikimedia_url(url)
    print("\nGET", url)
    response = client.get(url, headers={"Accept": "text/html"})
    response.raise_for_status()
    return response.text


def action_params(**extra: Any) -> dict[str, Any]:
    return {"action": "query", "format": "json", "formatversion": 2, **extra}


def pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get("query", {}).get("pages", [])


def print_json(value: Any, max_chars: int = 4_000) -> None:
    rendered = json.dumps(value, indent=2, ensure_ascii=False)
    print(rendered[:max_chars] + ("\n... output shortened ..." if len(rendered) > max_chars else ""))


def plain_snippet(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value))


# %% Bonus used by every article-producing example
def page_bonus_params(title: str) -> dict[str, Any]:
    """Fetch one page's information card and complete text, without images."""

    return action_params(
        titles=title,
        redirects=1,
        prop="extracts|pageterms|info|pageprops|revisions",
        explaintext=1,
        exsectionformat="plain",
        wbptterms="description",
        inprop="url",
        rvprop="ids|timestamp",
        rvlimit=1,
    )


def page_bonus_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result_pages = pages(payload)
    if not result_pages:
        raise ValueError("The page bonus response contained no pages")
    page = result_pages[0]
    descriptions = page.get("terms", {}).get("description", [])
    revisions = page.get("revisions", [])
    return {
        "card": {
            "page_id": page.get("pageid"),
            "title": page.get("title"),
            "canonical_url": page.get("canonicalurl") or page.get("fullurl"),
            "description": descriptions[0] if descriptions else None,
            "length_bytes": page.get("length"),
            "last_touched": page.get("touched"),
            "revision_id": revisions[0].get("revid") if revisions else None,
            "revision_timestamp": revisions[0].get("timestamp") if revisions else None,
            "wikidata_id": page.get("pageprops", {}).get("wikibase_item"),
            "is_disambiguation": "disambiguation" in page.get("pageprops", {}),
        },
        "full_plain_text": page.get("extract", ""),
    }


def print_first_page_bonus(title: str | None) -> None:
    """Print the requested bonus for one example's first article result."""

    if not title:
        print("BONUS: no article result was available")
        return
    bonus = page_bonus_from_payload(get_json(ACTION_API, page_bonus_params(title)))
    print("\nBONUS — FIRST RESULT PAGE CARD (NO IMAGE):")
    print_json(bonus["card"], 4_000)
    print("\nBONUS — FIRST RESULT COMPLETE PLAIN-TEXT CONTENT (NO IMAGE):")
    print(bonus["full_plain_text"])


def feed_page_title(page: dict[str, Any] | None) -> str | None:
    """Read a title from a Wikifeeds/Core REST page summary."""

    if not page:
        return None
    titles = page.get("titles", {})
    return titles.get("normalized") or page.get("title")


# %% Shared JSON dataset contract
def dataset_schema() -> dict[str, Any]:
    """Return the shared Draft 2020-12 schema for every generated dataset."""

    nullable_string = {"type": ["string", "null"]}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://wikipedia-doomscroll.local/page-results.schema.json",
        "title": "Wikipedia Doomscroll page results",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "example_id", "description", "retrieved_at",
            "wiki", "source", "expansion", "result_count", "pages",
        ],
        "properties": {
            "schema_version": {"const": "1.0.0"},
            "example_id": {"type": "string", "minLength": 1},
            "description": {"type": "string", "minLength": 1},
            "retrieved_at": {"type": "string", "format": "date-time"},
            "wiki": {"type": "string", "minLength": 1},
            "source": {
                "type": "object",
                "additionalProperties": False,
                "required": ["endpoint", "parameters"],
                "properties": {
                    "endpoint": {"type": "string", "format": "uri"},
                    "parameters": {"type": "object"},
                },
            },
            "expansion": {
                "type": "object",
                "additionalProperties": False,
                "required": ["mode", "anchor", "shortfall", "note"],
                "properties": {
                    "mode": {"enum": ["natural", "expanded"]},
                    "anchor": nullable_string,
                    "shortfall": {"type": "boolean"},
                    "note": nullable_string,
                },
            },
            "result_count": {"type": "integer", "minimum": 0, "maximum": 10},
            "pages": {
                "type": "array",
                "maxItems": 10,
                "items": {"$ref": "#/$defs/page"},
            },
        },
        "allOf": [
            {
                "if": {
                    "properties": {
                        "expansion": {
                            "properties": {"shortfall": {"const": False}},
                            "required": ["shortfall"],
                        }
                    }
                },
                "then": {
                    "properties": {
                        "result_count": {"const": 10},
                        "pages": {"minItems": 10},
                    }
                },
            }
        ],
        "$defs": {
            "page": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rank", "discovery", "identity", "card", "content"],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 10},
                    "discovery": {"type": "object"},
                    "identity": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "wiki", "page_id", "title", "canonical_url",
                            "revision_id", "revision_timestamp",
                        ],
                        "properties": {
                            "wiki": {"type": "string", "minLength": 1},
                            "page_id": {"type": "integer", "minimum": 1},
                            "title": {"type": "string", "minLength": 1},
                            "canonical_url": {"type": "string", "format": "uri"},
                            "revision_id": {"type": "integer", "minimum": 1},
                            "revision_timestamp": {"type": "string", "format": "date-time"},
                        },
                    },
                    "card": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "description", "wikidata_id", "length_bytes",
                            "last_touched", "is_disambiguation",
                        ],
                        "properties": {
                            "description": nullable_string,
                            "wikidata_id": nullable_string,
                            "length_bytes": {"type": "integer", "minimum": 0},
                            "last_touched": {"type": "string", "format": "date-time"},
                            "is_disambiguation": {"type": "boolean"},
                        },
                    },
                    "content": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["full_plain_text"],
                        "properties": {
                            "full_plain_text": {"type": "string", "minLength": 1}
                        },
                    },
                },
            }
        },
    }


def make_dataset_envelope(
    *,
    example_id: str,
    description: str,
    endpoint: str,
    parameters: dict[str, Any],
    expansion_mode: str,
    expansion_anchor: str | None,
    expansion_note: str | None,
    dataset_pages: list[dict[str, Any]],
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    shortfall = len(dataset_pages) < 10
    return {
        "schema_version": "1.0.0",
        "example_id": example_id,
        "description": description,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "wiki": f"{LANGUAGE}.wikipedia.org",
        "source": {"endpoint": endpoint, "parameters": parameters},
        "expansion": {
            "mode": expansion_mode,
            "anchor": expansion_anchor,
            "shortfall": shortfall,
            "note": expansion_note if expansion_note or not shortfall else "Upstream returned fewer than ten eligible articles.",
        },
        "result_count": len(dataset_pages),
        "pages": dataset_pages,
    }


def _contains_image_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.casefold() in {"image", "images", "thumbnail", "original_image"}
            or _contains_image_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_image_key(item) for item in value)
    return False


def validate_dataset(dataset: dict[str, Any]) -> None:
    """Validate the fixed schema contract without another runtime dependency."""

    def exact_keys(value: Any, expected: set[str], path: str) -> None:
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError(f"{path} must contain exactly {sorted(expected)}")

    exact_keys(
        dataset,
        {
            "schema_version", "example_id", "description", "retrieved_at",
            "wiki", "source", "expansion", "result_count", "pages",
        },
        "$",
    )
    if dataset["schema_version"] != "1.0.0":
        raise ValueError("unsupported schema_version")
    if not all(isinstance(dataset[key], str) and dataset[key] for key in ("example_id", "description", "retrieved_at", "wiki")):
        raise ValueError("dataset string metadata must be non-empty")
    exact_keys(dataset["source"], {"endpoint", "parameters"}, "source")
    if not str(dataset["source"]["endpoint"]).startswith("https://") or not isinstance(dataset["source"]["parameters"], dict):
        raise ValueError("source endpoint/parameters are invalid")
    exact_keys(dataset["expansion"], {"mode", "anchor", "shortfall", "note"}, "expansion")
    if dataset["expansion"]["mode"] not in {"natural", "expanded"}:
        raise ValueError("invalid expansion mode")
    if not isinstance(dataset["expansion"]["shortfall"], bool):
        raise ValueError("expansion.shortfall must be boolean")
    if not isinstance(dataset["pages"], list) or len(dataset["pages"]) > 10:
        raise ValueError("pages must be an array with at most ten values")
    if dataset["result_count"] != len(dataset["pages"]):
        raise ValueError("result_count does not match pages length")
    if not dataset["expansion"]["shortfall"] and len(dataset["pages"]) != 10:
        raise ValueError("a dataset without a shortfall must contain ten pages")

    expected_page_keys = {"rank", "discovery", "identity", "card", "content"}
    expected_identity_keys = {
        "wiki", "page_id", "title", "canonical_url", "revision_id",
        "revision_timestamp",
    }
    expected_card_keys = {
        "description", "wikidata_id", "length_bytes", "last_touched",
        "is_disambiguation",
    }
    for expected_rank, page in enumerate(dataset["pages"], start=1):
        exact_keys(page, expected_page_keys, f"pages[{expected_rank - 1}]")
        exact_keys(page["identity"], expected_identity_keys, "page.identity")
        exact_keys(page["card"], expected_card_keys, "page.card")
        exact_keys(page["content"], {"full_plain_text"}, "page.content")
        identity = page["identity"]
        card = page["card"]
        if page["rank"] != expected_rank or not isinstance(page["discovery"], dict):
            raise ValueError("page rank/discovery is invalid")
        if not isinstance(identity["page_id"], int) or identity["page_id"] < 1:
            raise ValueError("page_id must be a positive integer")
        if not isinstance(identity["revision_id"], int) or identity["revision_id"] < 1:
            raise ValueError("revision_id must be a positive integer")
        if not all(isinstance(identity[key], str) and identity[key] for key in ("wiki", "title", "canonical_url", "revision_timestamp")):
            raise ValueError("page identity strings must be non-empty")
        if not identity["canonical_url"].startswith("https://"):
            raise ValueError("canonical_url must use HTTPS")
        if not isinstance(card["length_bytes"], int) or card["length_bytes"] < 0:
            raise ValueError("length_bytes must be non-negative")
        if not isinstance(card["last_touched"], str) or not card["last_touched"]:
            raise ValueError("last_touched must be non-empty")
        if not isinstance(card["is_disambiguation"], bool):
            raise ValueError("is_disambiguation must be boolean")
        if not isinstance(page["content"]["full_plain_text"], str) or not page["content"]["full_plain_text"].strip():
            raise ValueError("full_plain_text must be non-empty")
    page_ids = [page["identity"]["page_id"] for page in dataset["pages"]]
    if len(page_ids) != len(set(page_ids)):
        raise ValueError("page IDs must be unique within a dataset")
    if _contains_image_key(dataset):
        raise ValueError("dataset contains a forbidden image field")


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def dedupe_titles(titles: list[str], limit: int | None = None) -> list[str]:
    """Dedupe titles in source order, treating spaces and underscores equally."""

    result: list[str] = []
    seen: set[str] = set()
    for title in titles:
        normalized = " ".join(title.replace("_", " ").split())
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
        if limit is not None and len(result) >= limit:
            break
    return result


def expand_with_related(
    initial_titles: list[str], related_titles: list[str], limit: int = 10
) -> list[str]:
    return dedupe_titles([*initial_titles, *related_titles], limit=limit)


def candidate(title: str | None, **discovery: Any) -> dict[str, Any] | None:
    if not title:
        return None
    return {"title": " ".join(title.replace("_", " ").split()), "discovery": discovery}


def dedupe_candidates(
    candidates: list[dict[str, Any] | None], limit: int = 10
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        if not item:
            continue
        key = item["title"].casefold()
        if key not in seen:
            seen.add(key)
            result.append(item)
        if len(result) >= limit:
            break
    return result


def dataset_specs() -> list[dict[str, Any]]:
    """Map every article-related notebook example to one output file."""

    action = f"https://{LANGUAGE}.wikipedia.org/w/api.php"
    analytics = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top"
    feed = f"https://{LANGUAGE}.wikipedia.org/api/rest_v1/feed"
    core = f"https://{LANGUAGE}.wikipedia.org/w/rest.php/v1"
    specs = [
        ("random-pages.json", "random-pages", "Random namespace-zero articles", "random", action, {"generator": "random", "limit": 20}, "natural", None),
        ("most-viewed-day.json", "most-viewed-day", "Most-viewed articles for 2026-07-20", "top-day", analytics, {"date": "2026-07-20", "access": "all-access"}, "natural", None),
        ("most-viewed-month.json", "most-viewed-month", "Most-viewed articles for June 2026", "top-month", analytics, {"year": 2026, "month": 6, "day": "all-days"}, "natural", None),
        ("most-viewed-year.json", "most-viewed-year", "Most-viewed articles aggregated across completed 2026 months", "top-year", analytics, {"year": 2026, "months": "completed"}, "natural", None),
        ("category-name-search.json", "category-name-search", "Articles expanded from category-name search for phys", "category-name", action, {"list": "prefixsearch", "query": "phys", "namespace": 14}, "expanded", "phys"),
        ("all-categories.json", "all-categories", "Articles expanded from the category index prefix Phys", "all-categories", action, {"list": "allcategories", "prefix": "Phys"}, "expanded", "Phys"),
        ("category-members.json", "category-members", "Article members of Category:Physics", "category-members", action, {"category": "Category:Physics", "member_type": "page"}, "natural", "Category:Physics"),
        ("category-subcategories.json", "category-subcategories", "Articles expanded from Physics subcategories", "category-subcategories", action, {"category": "Category:Physics", "member_type": "subcat"}, "expanded", "Category:Physics"),
        ("nearby-jerusalem.json", "nearby-jerusalem", "Articles near Jerusalem Old City", "nearby", action, {"latitude": 31.778, "longitude": 35.235, "radius_m": 10000}, "natural", "31.778|35.235"),
        ("featured.json", "featured", "Featured-feed articles for 2026-07-21", "featured", feed, {"date": "2026-07-21"}, "natural", "2026-07-21"),
        ("on-this-day.json", "on-this-day", "On-this-day articles for July 21", "on-this-day", feed, {"month": 7, "day": 21, "type": "all"}, "natural", "07-21"),
        ("full-text-search.json", "full-text-search", "Full-text results for Mongol Empire expansion", "full-text", action, {"query": "Mongol Empire expansion"}, "natural", "Mongol Empire expansion"),
        ("hydrated-search.json", "hydrated-search", "Hydrated search results for Mongol Empire expansion", "hydrated-search", action, {"query": "Mongol Empire expansion"}, "natural", "Mongol Empire expansion"),
        ("related-genghis-khan.json", "related-genghis-khan", "Articles related to Genghis Khan", "related", action, {"query": "morelike:Genghis_Khan"}, "natural", "Genghis Khan"),
        ("prefix-action.json", "prefix-action", "Action API title-prefix results for Genghis Khan", "prefix-action", action, {"prefix": "Genghis_Khan"}, "natural", "Genghis Khan"),
        ("prefix-core-rest.json", "prefix-core-rest", "Core REST title-prefix results for Genghis Khan", "prefix-core", core, {"q": "Genghis_Khan", "limit": 10}, "natural", "Genghis Khan"),
        ("page-card-hydration.json", "page-card-hydration", "Explicit page-card titles expanded with related articles", "anchor-related", action, {"titles": ["Genghis Khan", "Mongol Empire", "Kublai Khan"]}, "expanded", "Genghis Khan"),
        ("content-intro.json", "content-intro", "Intro-content example expanded from Genghis Khan", "anchor-related", action, {"content_option": "intro_plain_text", "title": "Genghis Khan"}, "expanded", "Genghis Khan"),
        ("content-full-text.json", "content-full-text", "Full-text example expanded from Genghis Khan", "anchor-related", action, {"content_option": "full_plain_text", "title": "Genghis Khan"}, "expanded", "Genghis Khan"),
        ("content-section.json", "content-section", "Parsed-section example expanded from Genghis Khan", "anchor-related", action, {"content_option": "parsed_section", "title": "Genghis Khan"}, "expanded", "Genghis Khan"),
        ("content-html.json", "content-html", "Rendered-HTML example expanded from Genghis Khan", "anchor-related", core, {"content_option": "current_html", "title": "Genghis Khan"}, "expanded", "Genghis Khan"),
        ("other-page-properties.json", "other-page-properties", "Other-properties example expanded from Genghis Khan", "anchor-related", action, {"content_option": "other_properties", "title": "Genghis Khan"}, "expanded", "Genghis Khan"),
    ]
    return [
        {
            "filename": filename,
            "example_id": example_id,
            "description": description,
            "kind": kind,
            "endpoint": endpoint,
            "parameters": parameters,
            "expansion_mode": expansion_mode,
            "anchor": anchor,
        }
        for filename, example_id, description, kind, endpoint, parameters, expansion_mode, anchor in specs
    ]


def _page_candidates(
    result_pages: list[dict[str, Any]], source: str
) -> list[dict[str, Any]]:
    ordered = sorted(result_pages, key=lambda page: page.get("index", 10_000))
    return dedupe_candidates(
        [
            candidate(
                page.get("title"),
                source=source,
                upstream_index=page.get("index"),
            )
            for page in ordered
        ],
        limit=50,
    )


def _related_candidates(limit: int = 50) -> list[dict[str, Any]]:
    params = action_params(
        generator="search",
        gsrsearch="morelike:Genghis_Khan",
        gsrnamespace=0,
        gsrlimit=limit,
        prop="info",
    )
    return _page_candidates(pages(get_json(ACTION_API, params)), "morelike:Genghis_Khan")


def _category_article_candidates(
    category_titles: list[str], limit: int = 10
) -> list[dict[str, Any]]:
    gathered: list[dict[str, Any] | None] = []
    for category_title in category_titles:
        member_pages = pages(
            get_json(ACTION_API, category_members(category_title, "page"))
        )
        gathered.extend(
            candidate(
                page.get("title"),
                source="categorymembers",
                category=category_title,
            )
            for page in member_pages
        )
        if len(dedupe_candidates(gathered, limit=limit)) >= limit:
            break
    return dedupe_candidates(gathered, limit=limit)


def discover_dataset_candidates(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Discover and expand ordered candidates for one dataset specification."""

    kind = spec["kind"]
    if kind == "random":
        params = action_params(
            generator="random",
            grnnamespace=0,
            grnfilterredir="nonredirects",
            grnminsize=1_000,
            grnlimit=20,
            prop="info",
        )
        return _page_candidates(pages(get_json(ACTION_API, params)), "random")
    if kind in {"top-day", "top-month"}:
        url = top_url(date(2026, 7, 20)) if kind == "top-day" else monthly_top_url(2026, 6)
        rows = top_articles(get_json(url))
        return dedupe_candidates(
            [candidate(row.get("article"), source=kind, views=row.get("views")) for row in rows],
            limit=50,
        )
    if kind == "top-year":
        return [
            {"title": title.replace("_", " "), "discovery": {"source": kind, "views": views}}
            for title, views in yearly_top(2026, limit=50)
        ]
    if kind == "category-name":
        payload = get_json(
            ACTION_API,
            action_params(list="prefixsearch", pssearch="phys", psnamespace=14, pslimit=10),
        )
        categories = [item["title"] for item in payload.get("query", {}).get("prefixsearch", [])]
        return _category_article_candidates(categories)
    if kind == "all-categories":
        payload = get_json(
            ACTION_API,
            action_params(list="allcategories", acprefix="Phys", aclimit=10),
        )
        rows = payload.get("query", {}).get("allcategories", [])
        categories = [
            f"Category:{row.get('category') or row.get('*')}"
            for row in rows
            if row.get("category") or row.get("*")
        ]
        return _category_article_candidates(categories)
    if kind == "category-members":
        return _page_candidates(
            pages(get_json(ACTION_API, category_members("Physics", "page"))),
            "Category:Physics",
        )[:10]
    if kind == "category-subcategories":
        subcategories = pages(
            get_json(ACTION_API, category_members("Physics", "subcat"))
        )
        return _category_article_candidates(
            [page["title"] for page in subcategories if page.get("title")]
        )
    if kind == "nearby":
        result = pages(get_json(ACTION_API, nearby_params))
        return dedupe_candidates(
            [
                candidate(
                    page.get("title"),
                    source="geosearch",
                    upstream_index=page.get("index"),
                    coordinates=page.get("coordinates"),
                )
                for page in result
            ]
        )
    if kind == "featured":
        payload = get_json(featured_url)
        summaries = [payload.get("tfa"), *payload.get("mostread", {}).get("articles", [])]
        return dedupe_candidates(
            [candidate(feed_page_title(item), source="featured") for item in summaries]
        )
    if kind == "on-this-day":
        payload = get_json(on_this_day_url)
        gathered: list[dict[str, Any] | None] = []
        for event in payload.get("events", []):
            gathered.extend(
                candidate(
                    feed_page_title(page),
                    source="on-this-day",
                    year=event.get("year"),
                    event_text=event.get("text"),
                )
                for page in event.get("pages", [])
            )
        return dedupe_candidates(gathered)
    if kind == "full-text":
        payload = get_json(ACTION_API, {**full_text_params, "srlimit": 20})
        return dedupe_candidates(
            [
                candidate(
                    item.get("title"),
                    source="full-text-search",
                    wordcount=item.get("wordcount"),
                    timestamp=item.get("timestamp"),
                )
                for item in payload.get("query", {}).get("search", [])
            ]
        )
    if kind == "hydrated-search":
        return _page_candidates(
            pages(get_json(ACTION_API, {**hydrated_search_params, "gsrlimit": 20})),
            "hydrated-search",
        )[:10]
    if kind == "related":
        return _related_candidates()[:10]
    if kind == "prefix-action":
        return _page_candidates(
            pages(get_json(ACTION_API, {**prefix_params, "gpslimit": 20})),
            "prefix-action",
        )[:10]
    if kind == "prefix-core":
        payload = get_json(f"{CORE_REST}/search/title", {"q": "Genghis_Khan", "limit": 20})
        return dedupe_candidates(
            [candidate(feed_page_title(item), source="prefix-core-rest") for item in payload.get("pages", [])]
        )
    if kind == "anchor-related":
        initial = spec["parameters"].get("titles", ["Genghis Khan"])
        related = _related_candidates()
        by_title = [candidate(title, source="explicit-anchor") for title in initial]
        by_title.extend(related)
        return dedupe_candidates(by_title)
    raise ValueError(f"Unknown dataset kind: {kind}")


def _title_key(title: str) -> str:
    return " ".join(title.replace("_", " ").split()).casefold()


def hydrate_dataset_pages(
    candidates: list[dict[str, Any]],
    payload: dict[str, Any],
    *,
    require_content: bool = True,
    max_pages: int = 10,
) -> list[dict[str, Any]]:
    """Normalize a hydration payload while restoring candidate source order."""

    query = payload.get("query", {})
    aliases: dict[str, str] = {}
    for field in ("normalized", "redirects"):
        for mapping in query.get(field, []):
            source = mapping.get("from")
            target = mapping.get("to")
            if source and target:
                aliases[_title_key(source)] = _title_key(target)

    def resolve(key: str) -> str:
        seen: set[str] = set()
        while key in aliases and key not in seen:
            seen.add(key)
            key = aliases[key]
        return key

    by_title = {
        _title_key(page.get("title", "")): page
        for page in query.get("pages", [])
        if isinstance(page, dict) and page.get("title")
    }
    hydrated: list[dict[str, Any]] = []
    seen_page_ids: set[int] = set()
    for source_candidate in candidates:
        page = by_title.get(resolve(_title_key(source_candidate["title"])))
        if not page or page.get("missing") or page.get("ns") != 0:
            continue
        pageprops = page.get("pageprops", {})
        revisions = page.get("revisions", [])
        extract = page.get("extract", "")
        page_id = page.get("pageid")
        if (
            "disambiguation" in pageprops
            or not isinstance(page_id, int)
            or page_id in seen_page_ids
            or not revisions
            or (require_content and not extract.strip())
        ):
            continue
        seen_page_ids.add(page_id)
        descriptions = page.get("terms", {}).get("description", [])
        revision = revisions[0]
        hydrated.append(
            {
                "rank": len(hydrated) + 1,
                "discovery": source_candidate.get("discovery", {}),
                "identity": {
                    "wiki": f"{LANGUAGE}.wikipedia.org",
                    "page_id": page_id,
                    "title": page["title"],
                    "canonical_url": page.get("canonicalurl") or page.get("fullurl"),
                    "revision_id": revision.get("revid"),
                    "revision_timestamp": revision.get("timestamp"),
                },
                "card": {
                    "description": descriptions[0] if descriptions else None,
                    "wikidata_id": pageprops.get("wikibase_item"),
                    "length_bytes": page.get("length", 0),
                    "last_touched": page.get("touched"),
                    "is_disambiguation": False,
                },
                "content": {"full_plain_text": extract},
            }
        )
        if len(hydrated) == max_pages:
            break
    return hydrated


_FULL_TEXT_CACHE: dict[str, str] = {}


def _fetch_full_plain_text(title: str) -> str:
    key = _title_key(title)
    if key in _FULL_TEXT_CACHE:
        return _FULL_TEXT_CACHE[key]
    params = action_params(
        titles=title,
        redirects=1,
        prop="extracts",
        explaintext=1,
        exsectionformat="plain",
    )
    result_pages = pages(get_json(ACTION_API, params))
    text = result_pages[0].get("extract", "") if result_pages else ""
    if text.strip():
        _FULL_TEXT_CACHE[key] = text
        if result_pages[0].get("title"):
            _FULL_TEXT_CACHE[_title_key(result_pages[0]["title"])] = text
    return text


def hydrate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Batch card metadata, then fetch/cache one full extract per eligible page."""

    selected = candidates[:50]
    if not selected:
        return []
    params = action_params(
        titles="|".join(item["title"] for item in selected),
        redirects=1,
        prop="pageterms|info|pageprops|revisions",
        wbptterms="description",
        inprop="url",
        rvprop="ids|timestamp",
    )
    hydrated = hydrate_dataset_pages(
        selected,
        get_json(ACTION_API, params),
        require_content=False,
        max_pages=50,
    )
    with_content: list[dict[str, Any]] = []
    for page in hydrated:
        text = _fetch_full_plain_text(page["identity"]["title"])
        if not text.strip():
            continue
        page["content"]["full_plain_text"] = text
        page["rank"] = len(with_content) + 1
        with_content.append(page)
        if len(with_content) == 10:
            break
    return with_content


def generate_all_datasets(
    output_dir: Path = Path("wikimedia_content"),
    example_ids: set[str] | None = None,
) -> list[Path]:
    """Generate and validate every example snapshot plus the shared schema."""

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_dir / "page-results.schema.json", dataset_schema())
    retrieved_at = datetime.now(timezone.utc).isoformat()
    written: list[Path] = []
    for spec in dataset_specs():
        if example_ids is not None and spec["example_id"] not in example_ids:
            continue
        print(f"\nGENERATING {spec['filename']}")
        candidates = discover_dataset_candidates(spec)
        dataset_pages = hydrate_candidates(candidates)
        expansion_note = (
            "Expanded deterministically from the recorded anchor to reach ten articles."
            if spec["expansion_mode"] == "expanded"
            else None
        )
        dataset = make_dataset_envelope(
            example_id=spec["example_id"],
            description=spec["description"],
            endpoint=spec["endpoint"],
            parameters=spec["parameters"],
            expansion_mode=spec["expansion_mode"],
            expansion_anchor=spec["anchor"],
            expansion_note=expansion_note,
            dataset_pages=dataset_pages,
            retrieved_at=retrieved_at,
        )
        validate_dataset(dataset)
        destination = output_dir / spec["filename"]
        write_json_atomic(destination, dataset)
        written.append(destination)
        print(f"WROTE {destination} ({len(dataset_pages)} pages)")
    return written


# %% Random pages
# `generator=random` discovers pages and hydrates their cards in one request.
random_params = action_params(
    generator="random",
    grnnamespace=0,                 # encyclopedia articles only
    grnfilterredir="nonredirects",
    grnminsize=1_000,               # optional quality floor in bytes
    grnlimit=5,
    prop="extracts|pageimages|pageterms|info|pageprops",
    exintro=1,
    explaintext=1,
    exchars=500,
    piprop="thumbnail|original",
    pithumbsize=640,
    wbptterms="description",
    inprop="url",
)

if RUN_LIVE_EXAMPLES:
    random_result = get_json(ACTION_API, random_params)
    random_pages = pages(random_result)
    for page in random_pages:
        print_json(
            {
                "pageid": page.get("pageid"),
                "title": page.get("title"),
                "description": page.get("terms", {}).get("description", [None])[0],
                "extract": page.get("extract"),
                "thumbnail": page.get("thumbnail", {}).get("source"),
            },
            1_500,
        )
    print_first_page_bonus(random_pages[0].get("title") if random_pages else None)

# Random is a sequence from a random starting point, not a perfect independent
# sample. A feed should deduplicate and suppress recently served articles.


# %% Most-viewed pages: day
def top_url(day: date) -> str:
    return (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
        f"en.wikipedia.org/all-access/{day:%Y/%m/%d}"
    )


def top_articles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items", [])
    return items[0].get("articles", []) if items else []


if RUN_LIVE_EXAMPLES:
    # Use a completed day; Analytics is aggregated and delayed.
    daily = top_articles(get_json(top_url(date(2026, 7, 20))))
    print("Daily top 10:")
    print_json([{"title": x["article"], "views": x["views"]} for x in daily[:10]])
    print_first_page_bonus(daily[0].get("article") if daily else None)


# %% Most-viewed pages: month
def monthly_top_url(year: int, month: int) -> str:
    return (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
        f"en.wikipedia.org/all-access/{year:04d}/{month:02d}/all-days"
    )


if RUN_LIVE_EXAMPLES:
    monthly = top_articles(get_json(monthly_top_url(2026, 6)))
    print("June 2026 top 10:")
    print_json([{"title": x["article"], "views": x["views"]} for x in monthly[:10]])
    print_first_page_bonus(monthly[0].get("article") if monthly else None)


# %% Most-viewed pages: year
# There is no direct annual top endpoint. Fetch the 12 monthly lists, cache each
# response, sum matching article titles, and sort locally (12 requests total).
def yearly_top(year: int, limit: int = 25) -> list[tuple[str, int]]:
    totals: Counter[str] = Counter()
    last_complete_month = 12 if year < date.today().year else date.today().month - 1
    for month in range(1, last_complete_month + 1):
        for article in top_articles(get_json(monthly_top_url(year, month))):
            title, views = article.get("article"), article.get("views")
            if isinstance(title, str) and isinstance(views, int):
                totals[title] += views
    return totals.most_common(limit)


if RUN_LIVE_EXAMPLES:
    print("2026 year-to-date top 25, aggregated from completed monthly lists:")
    annual = yearly_top(2026)
    print_json(annual)
    print_first_page_bonus(annual[0][0] if annual else None)

# Top lists include `Main_Page`, special pages, bots, and news spikes. Resolve
# titles through Action API and filter namespace 0 before using them in a feed.


# %% Category discovery: find category names
# Wikipedia does not have a small static list of categories. Categories are a
# changing, community-maintained graph. Search names with namespace 14:
category_name_params = action_params(
    list="prefixsearch", pssearch="phys", psnamespace=14, pslimit=10
)

if RUN_LIVE_EXAMPLES:
    category_names = get_json(ACTION_API, category_name_params)
    print("Category names beginning with 'phys':")
    print_json(category_names["query"]["prefixsearch"])


# %% Category discovery: enumerate all category names
# `list=allcategories` walks the alphabetical category index. Always round-trip
# the returned `continue` object unchanged for the next page. For millions of
# categories or offline analysis, use official Wikimedia dumps instead.
all_categories_params = action_params(
    list="allcategories", acprefix="Phys", aclimit=20, acprop="size|hidden"
)

if RUN_LIVE_EXAMPLES:
    all_categories = get_json(ACTION_API, all_categories_params)
    print_json(all_categories["query"]["allcategories"])
    print("Opaque next-page values:", all_categories.get("continue"))


# %% Category discovery: pages and subcategories
def category_members(category: str, member_type: str) -> dict[str, Any]:
    namespace = 0 if member_type == "page" else 14
    title = category if category.startswith("Category:") else f"Category:{category}"
    return action_params(
        generator="categorymembers",
        gcmtitle=title,
        gcmnamespace=namespace,
        gcmtype=member_type,
        gcmlimit=20,
        prop="extracts|pageterms|info" if member_type == "page" else "info",
        exintro=1,
        explaintext=1,
        exchars=350,
        wbptterms="description",
        inprop="url",
    )


if RUN_LIVE_EXAMPLES:
    print("Article members of Category:Physics:")
    physics_pages = pages(get_json(ACTION_API, category_members("Physics", "page")))
    print_json(physics_pages)
    print_first_page_bonus(physics_pages[0].get("title") if physics_pages else None)
    print("Immediate subcategories of Category:Physics:")
    print_json(pages(get_json(ACTION_API, category_members("Physics", "subcat"))))

# Category graphs contain cycles and maintenance categories. Recursive crawlers
# need a visited set plus strict depth, request, and result limits.


# %% Nearby / geospatial discovery
nearby_params = action_params(
    generator="geosearch",
    ggscoord="31.778|35.235",       # latitude|longitude: Jerusalem Old City
    ggsradius=10_000,                # meters; results are distance ordered
    ggsnamespace=0,
    ggslimit=10,
    prop="coordinates|extracts|pageimages|pageterms|info",
    exintro=1,
    explaintext=1,
    exchars=400,
    pithumbsize=320,
    wbptterms="description",
    inprop="url",
)

if RUN_LIVE_EXAMPLES:
    nearby = pages(get_json(ACTION_API, nearby_params))
    for page in nearby:
        print_json(
            {
                "title": page.get("title"),
                "coordinates": page.get("coordinates"),
                "extract": page.get("extract"),
            },
            1_000,
        )
    print_first_page_bonus(nearby[0].get("title") if nearby else None)

# Treat precise user coordinates as sensitive data; do not persist them unless
# the product actually requires it.


# %% Featured and on-this-day content
featured_url = f"https://{LANGUAGE}.wikipedia.org/api/rest_v1/feed/featured/2026/07/21"
on_this_day_url = f"https://{LANGUAGE}.wikipedia.org/api/rest_v1/feed/onthisday/all/07/21"

if RUN_LIVE_EXAMPLES:
    featured = get_json(featured_url)
    print("Featured response sections:", sorted(featured))
    print_json(featured, 3_000)
    print_first_page_bonus(feed_page_title(featured.get("tfa")))

    on_this_day = get_json(on_this_day_url)
    print("First two on-this-day events:")
    events = on_this_day.get("events", [])
    print_json(events[:2], 3_000)
    event_pages = events[0].get("pages", []) if events else []
    print_first_page_bonus(feed_page_title(event_pages[0] if event_pages else None))

# On-this-day supports variants such as events, births, deaths, holidays, and
# selected where the language wiki provides them. Featured is unstable and
# on-this-day is experimental, so isolate these routes behind an adapter with
# schema checks, cached last-known-good content, and a kill switch.


# %% 4. Search endpoints: full-text search
# This returns ranked matches plus HTML-highlighted snippets. It does not return
# clean article summaries. `sroffset` and the response `continue` paginate.
full_text_params = action_params(
    list="search",
    srsearch="Mongol Empire expansion",
    srnamespace=0,
    srlimit=10,
    sroffset=0,
    srinfo="suggestion|totalhits",
    srprop="size|wordcount|timestamp|snippet",
    srsort="relevance",
)

if RUN_LIVE_EXAMPLES:
    search = get_json(ACTION_API, full_text_params)
    matches = search["query"]["search"]
    for match in matches:
        print(
            {
                "title": match["title"],
                "plain_snippet": plain_snippet(match.get("snippet", "")),
                "wordcount": match.get("wordcount"),
            }
        )
    print("Next-page values:", search.get("continue"))
    print_first_page_bonus(matches[0].get("title") if matches else None)

# Useful CirrusSearch examples for `srsearch`:
#   intitle:"Genghis Khan"       title contains this phrase
#   incategory:"Mongol khans"    member of this category
#   morelike:Genghis_Khan        content-similar articles
# Sort options include relevance, create_timestamp_desc, last_edit_desc,
# incoming_links_desc, and random/user_random.


# %% Search and hydrate cards in one request
hydrated_search_params = action_params(
    generator="search",
    gsrsearch="Mongol Empire expansion",
    gsrnamespace=0,
    gsrlimit=10,
    prop="extracts|pageimages|pageterms|info|pageprops",
    exintro=1,
    explaintext=1,
    exchars=500,
    piprop="thumbnail|original",
    pithumbsize=640,
    wbptterms="description",
    inprop="url",
)

if RUN_LIVE_EXAMPLES:
    hydrated_search = pages(get_json(ACTION_API, hydrated_search_params))
    # Preserve each page's `index`; it is the search rank.
    ranked_search = sorted(hydrated_search, key=lambda item: item.get("index", 9999))
    for page in ranked_search:
        print_json(page, 1_500)
    print_first_page_bonus(ranked_search[0].get("title") if ranked_search else None)


# %% Related articles: Genghis_Khan
# The old `/api/rest_v1/page/related/{title}` route is gone. Use CirrusSearch's
# content-similarity operator. This is search behavior, not a stable recommender.
related_params = action_params(
    generator="search",
    gsrsearch="morelike:Genghis_Khan",
    gsrnamespace=0,
    gsrlimit=10,
    prop="extracts|pageimages|pageterms|info",
    exintro=1,
    explaintext=1,
    exchars=400,
    pithumbsize=320,
    wbptterms="description",
    inprop="url",
)

if RUN_LIVE_EXAMPLES:
    related = pages(get_json(ACTION_API, related_params))
    print("Articles related by content to Genghis Khan:")
    ranked_related = sorted(related, key=lambda item: item.get("index", 9999))
    for page in ranked_related:
        print(page.get("title"), "—", page.get("extract", "")[:180])
    print_first_page_bonus(ranked_related[0].get("title") if ranked_related else None)


# %% Prefix / typeahead search: Genghis_Khan
# Prefix search only asks: "which titles begin with these characters?" It is
# different from full-text search and from related-article search.
prefix_params = action_params(
    generator="prefixsearch",
    gpssearch="Genghis_Khan",
    gpsnamespace=0,
    gpslimit=10,
    prop="pageimages|pageterms|info",
    piprop="thumbnail",
    pithumbsize=80,
    wbptterms="description",
    inprop="url",
)

if RUN_LIVE_EXAMPLES:
    action_typeahead = pages(get_json(ACTION_API, prefix_params))
    print("Action API typeahead with hydrated fields:")
    print_json(action_typeahead)
    print_first_page_bonus(
        action_typeahead[0].get("title") if action_typeahead else None
    )

    core_typeahead = get_json(
        f"{CORE_REST}/search/title", {"q": "Genghis_Khan", "limit": 10}
    )
    print("Core REST's simpler title typeahead:")
    print_json(core_typeahead)
    core_pages = core_typeahead.get("pages", [])
    print_first_page_bonus(feed_page_title(core_pages[0] if core_pages else None))


# %% 5. Page-card hydration: all useful options in one batch
# Up to 50 titles/page IDs is the normal Action API batch limit. `redirects=1`
# resolves moved/redirected titles. Toggle fields by changing `prop` and the
# matching property-specific options below.
card_params = action_params(
    titles="Genghis Khan|Mongol Empire|Kublai Khan",
    redirects=1,
    prop="extracts|pageimages|pageterms|info|pageprops|revisions",
    exintro=1,                       # intro only; remove for a full extract
    explaintext=1,                   # clean plain text, not HTML
    exchars=500,                     # shorten card text
    piprop="thumbnail|original",    # representative image options
    pithumbsize=640,
    wbptterms="description",        # Wikidata short description
    inprop="url",                   # canonical/full/edit URLs
    rvprop="ids|timestamp",         # current content identity, not history
    rvlimit=1,
)


def normalize_card(page: dict[str, Any]) -> dict[str, Any]:
    descriptions = page.get("terms", {}).get("description", [])
    revisions = page.get("revisions", [])
    return {
        "page_id": page.get("pageid"),
        "title": page.get("title"),
        "canonical_url": page.get("canonicalurl") or page.get("fullurl"),
        "description": descriptions[0] if descriptions else None,
        "intro_extract": page.get("extract"),
        "length_bytes": page.get("length"),
        "last_touched": page.get("touched"),
        "revision_id": revisions[0].get("revid") if revisions else None,
        "revision_timestamp": revisions[0].get("timestamp") if revisions else None,
        "wikidata_id": page.get("pageprops", {}).get("wikibase_item"),
        "is_disambiguation": "disambiguation" in page.get("pageprops", {}),
        "thumbnail": page.get("thumbnail"),
        "original_image": page.get("original"),
    }


if RUN_LIVE_EXAMPLES:
    raw_cards = pages(get_json(ACTION_API, card_params))
    for raw_page in raw_cards:
        print("\nRAW PAGE FIELDS:")
        print_json(raw_page, 3_000)
        print("NORMALIZED CARD:")
        print_json(normalize_card(raw_page), 3_000)
    print_first_page_bonus(raw_cards[0].get("title") if raw_cards else None)

# Field map:
#   extracts   -> intro/full text (`exintro`, `explaintext`, `exchars`)
#   pageimages -> representative thumbnail/original (`piprop`, `pithumbsize`)
#   pageterms  -> Wikidata short description (`wbptterms=description`)
#   info       -> length, touched time, canonical URL (`inprop=url`)
#   pageprops  -> Wikidata QID and disambiguation marker
#   revisions  -> current revision ID/timestamp for cache identity
# PageImages is a representative-image heuristic. Image licensing must be
# retrieved separately from Commons before reusing an image.


# %% Full content option 1: intro-only plain text
# This is the simplest clean card text: no images, rendered citation links, or
# HTML. It returns the lead section only.
intro_content_params = action_params(
    titles="Genghis Khan",
    prop="extracts|info|pageprops",
    exintro=1,
    explaintext=1,
    inprop="url",
)

if RUN_LIVE_EXAMPLES:
    intro_page = pages(get_json(ACTION_API, intro_content_params))[0]
    print(intro_page["extract"])
    print_first_page_bonus(intro_page.get("title"))


# %% Full content option 2: complete plain text
# Remove `exintro` to get the whole article as plain text. Use this when section
# structure is not important. `exsectionformat=plain` keeps headings readable.
full_text_content_params = action_params(
    titles="Genghis Khan",
    prop="extracts|info|pageprops",
    explaintext=1,
    exsectionformat="plain",
    inprop="url",
)

if RUN_LIVE_EXAMPLES:
    full_text_page = pages(get_json(ACTION_API, full_text_content_params))[0]
    print(full_text_page["extract"][:8_000])
    print_first_page_bonus(full_text_page.get("title"))


# %% Full content option 3: list sections, then fetch only one section
# `action=parse&prop=sections` returns indices and headings, not article text.
# Select an index, then request only that section's parsed HTML.
section_list_params = {
    "action": "parse",
    "format": "json",
    "formatversion": 2,
    "page": "Genghis Khan",
    "prop": "sections",
}


class _ArticleTextParser(HTMLParser):
    """Small standard-library cleaner for Wikimedia's parsed HTML."""

    block_tags = {"h1", "h2", "h3", "h4", "p", "li"}
    skipped_tags = {"script", "style", "img", "picture", "figure", "table", "nav", "aside"}
    void_tags = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
    skipped_classes = {
        "reference", "mw-editsection", "reflist", "references", "navbox",
        "vertical-navbox", "metadata", "ambox", "toc",
    }
    excluded_sections = {"references", "notes", "citations", "external links"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.skip_depth = 0
        self.current_block: str | None = None
        self.buffer: list[str] = []
        self.excluded_heading_level: int | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        classes = set(dict(attrs).get("class", "").split())
        if self.skip_depth:
            if tag not in self.void_tags:
                self.skip_depth += 1
            return
        if tag in self.skipped_tags or classes & self.skipped_classes:
            if tag not in self.void_tags:
                self.skip_depth = 1
            return
        if re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            if self.excluded_heading_level is not None and level <= self.excluded_heading_level:
                self.excluded_heading_level = None
        if tag in self.block_tags and self.current_block is None:
            self.current_block = tag
            self.buffer = []

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag != self.current_block:
            return
        text = " ".join("".join(self.buffer).split())
        if tag.startswith("h") and text.casefold() in self.excluded_sections:
            self.excluded_heading_level = int(tag[1])
        elif text and self.excluded_heading_level is None:
            self.lines.append(text)
        self.current_block = None
        self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.current_block is not None and not self.skip_depth:
            self.buffer.append(data)


def clean_article_html(raw_html: str) -> str:
    """Keep headings/paragraphs/lists; remove images, citations, and references."""

    parser = _ArticleTextParser()
    parser.feed(raw_html)
    return "\n\n".join(parser.lines)


if RUN_LIVE_EXAMPLES:
    section_index = get_json(ACTION_API, section_list_params)["parse"]["sections"]
    print("Available sections:")
    print_json([{"index": s["index"], "title": s["line"]} for s in section_index])

    # Prefer a recognizable section, but tolerate future heading changes.
    chosen = next(
        (s for s in section_index if "early life" in s["line"].casefold()),
        section_index[0],
    )
    one_section_params = {
        "action": "parse",
        "format": "json",
        "formatversion": 2,
        "page": "Genghis Khan",
        "section": chosen["index"],
        "prop": "text|displaytitle",
        "parser": "parsoid",
    }
    section_payload = get_json(ACTION_API, one_section_params)
    section_html = section_payload["parse"]["text"]
    print(f"Cleaned section: {chosen['line']}")
    print(clean_article_html(section_html)[:6_000])
    print_first_page_bonus("Genghis Khan")


# %% Full content option 4: current rendered article HTML
# Core REST `/html` provides the current Parsoid HTML. This is the best option
# when document structure matters. It is API HTML, not scraped website HTML.
article_title = quote("Genghis Khan", safe="")
core_html_url = f"{CORE_REST}/page/{article_title}/html"

if RUN_LIVE_EXAMPLES:
    full_html = get_html(core_html_url)
    print("Raw HTML characters:", len(full_html))
    print("Clean prose preview:")
    print(clean_article_html(full_html)[:8_000])
    print_first_page_bonus("Genghis Khan")


# %% Other page properties
# Ask only for properties you need. Each list-like property can return its own
# continuation key, so send the entire returned `continue` object unchanged.
other_properties_params = action_params(
    titles="Genghis Khan",
    prop="categories|links|extlinks|coordinates|langlinks|pageprops",
    clshow="!hidden",
    cllimit=20,
    pllimit=20,
    ellimit=20,
    lllimit=20,
)

if RUN_LIVE_EXAMPLES:
    property_payload = get_json(ACTION_API, other_properties_params)
    property_page = pages(property_payload)[0]
    print_json(
        {
            "categories": property_page.get("categories"),
            "internal_links": property_page.get("links"),
            "external_links": property_page.get("extlinks"),
            "coordinates": property_page.get("coordinates"),
            "language_links": property_page.get("langlinks"),
            "page_properties": property_page.get("pageprops"),
            "continue": property_payload.get("continue"),
        },
        8_000,
    )
    print_first_page_bonus(property_page.get("title"))


# %% Access and rate limits: getting approximately 200 requests/minute
RATE_LIMIT_GUIDE = """
Public Wikipedia reads do not need an API key.

To qualify for Wikimedia's normal identified anonymous class (currently about
200 requests/minute), send a descriptive User-Agent containing:
  1. your application name and version;
  2. a real monitored email address or HTTPS contact page;
  3. your HTTP library/version.

This file sends:
  {user_agent}

Important:
- An unidentified server/IP automation class may be limited to about 10/minute.
- Browser JavaScript cannot set User-Agent; use `Api-User-Agent`, though a
  backend proxy is preferred for caching, retries, identity, and schemas.
- Keep concurrency at three requests or fewer. This file is sequential.
- Batch up to 50 normal page titles/IDs in one Action API query.
- Cache daily/monthly rankings and hydrated cards; do not call per swipe.
- Honor HTTP 429/503 and Retry-After. Without Retry-After, wait at least five
  seconds and use bounded exponential backoff.
- `maxlag=5` is considerate for non-interactive Action API jobs.
- OAuth is for authenticated/write operations or authenticated rate classes;
  it is not required for ordinary public reads.
- If you need sustained bulk or commercial access, use Wikimedia dumps or
  contact Wikimedia Enterprise. Do not rotate IPs/accounts to evade limits.

Current limits can change. Recheck:
https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
https://www.mediawiki.org/wiki/API:Etiquette
""".format(user_agent=HEADERS["User-Agent"])

print(RATE_LIMIT_GUIDE)


# %% Official documentation used
OFFICIAL_SOURCES = [
    "https://www.mediawiki.org/wiki/API:Search_and_discovery",
    "https://www.mediawiki.org/wiki/API:Query",
    "https://www.mediawiki.org/wiki/API:REST_API/Reference",
    "https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/",
    "https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits",
    "https://www.mediawiki.org/wiki/API:Etiquette",
    "https://www.mediawiki.org/wiki/Wikimedia_APIs/Changelog",
    f"https://{LANGUAGE}.wikipedia.org/wiki/Special:RestSandbox",
]

print("Official references:")
print("\n".join(f"- {url}" for url in OFFICIAL_SOURCES))


if GENERATE_JSON_DATASETS:
    generated_files = generate_all_datasets(example_ids=GENERATE_JSON_ONLY)
    print(f"Generated {len(generated_files)} dataset files.")


if RUN_LIVE_EXAMPLES:
    client.close()
