import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.db import connect, get_connection, migrate
from app.enrich import run_directory
from app.enrichment import ArticleDossier, EnrichmentPipeline, validate_dossier
from app.enrichment_repository import get_post_enrichment
from app.enrichment_routes import router as enrichment_router
from app.openai_client import OpenAIClient, Usage, estimate_cost
from app.post_generation import GeneratedPost, generate_pending_posts


DOSSIER = {
    "summary": "A person overcame institutional resistance to create lasting work.",
    "article_type": "biography",
    "entities": [{"name": "Ada", "type": "person", "role": "subject"}],
    "places": ["London"],
    "time_periods": [
        {
            "label": "Victorian era",
            "start_year": 1837,
            "end_year": 1901,
            "significance": "The surrounding social context.",
        }
    ],
    "key_facts": [
        {"id": "f1", "claim": "She published influential work.", "evidence": "published influential work"}
    ],
    "human_stakes": [
        {
            "category": "victory",
            "description": "Her ideas endured.",
            "affected_people": ["Ada"],
            "evidence_ids": ["f1"],
        }
    ],
    "emotional_dimensions": [],
    "political_dimensions": [],
    "social_dimensions": [],
    "narrative_material": [
        {
            "pattern": "relevance-today",
            "description": "The work shaped later computing.",
            "evidence_ids": ["f1"],
        }
    ],
    "engagement_material": [
        {
            "mechanism": "curiosity",
            "insight": "The work preceded modern computers.",
            "why_people_care": "It changes assumptions about computing history.",
            "evidence_ids": ["f1"],
        }
    ],
    "sensitivities": [],
}

SYNTHESIS = {
    "tags": [
        {
            "kind": "topic",
            "slug": "computing-history",
            "label": "Computing history",
            "taxonomy_path": ["technology", "computing-history"],
            "confidence": 0.95,
            "rationale": "The work influenced computing.",
            "rank": 1,
            "evidence_ids": ["f1"],
        },
        {
            "kind": "topic",
            "slug": "Computing history!",
            "label": "Computing history duplicate",
            "taxonomy_path": ["technology", "computing-history"],
            "confidence": 0.90,
            "rationale": "Duplicate wording.",
            "rank": 2,
            "evidence_ids": ["f1"],
        },
        {
            "kind": "theme",
            "slug": "weak",
            "label": "Weak",
            "taxonomy_path": [],
            "confidence": 0.40,
            "rationale": "Too weak to keep.",
            "rank": 3,
            "evidence_ids": ["f1"],
        },
    ],
    "engagement_angles": [
        {
            "rank": 1,
            "emotional_mechanism": "surprise",
            "hook": "The idea arrived before the machine.",
            "why_it_matters": "It reverses a familiar technology story.",
            "affected_people": ["Ada"],
            "sensitivity_level": "low",
            "evidence_ids": ["f1"],
        }
    ],
}

GENERATED_POST = {
    "character_name": "Ada Lovelace",
    "character_description": "A mathematician writing from computing's prehistory.",
    "title": "You built the machine. I wrote its future.",
    "content": "I published the work before modern computers existed. So why does history still act as if imagination only follows invention? My notes did not wait for permission from a machine—or from anyone who thought the future belonged to them.",
    "historical_start_year": 1843,
    "historical_end_year": None,
    "historical_precision": "year",
    "historical_date_label": "1843",
    "evidence_ids": ["f1"],
}


class TinyOutput(BaseModel):
    value: int


class FakeResponses:
    def __init__(self, *, fail_on_synthesis: bool = False) -> None:
        self.calls: list[dict[str, object]] = []
        self.fail_on_synthesis = fail_on_synthesis

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        output_type = kwargs["text_format"]
        if self.fail_on_synthesis and output_type.__name__ == "DiscoverySynthesis":
            raise FakeAPIError("synthesis failed")
        if output_type.__name__ == "ArticleDossier":
            output = output_type.model_validate(DOSSIER)
        elif output_type.__name__ == "DiscoverySynthesis":
            output = output_type.model_validate(SYNTHESIS)
        elif output_type.__name__ == "GeneratedPost":
            output = output_type.model_validate(GENERATED_POST)
        else:
            output = output_type(value=7)
        usage = SimpleNamespace(
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            input_tokens_details=SimpleNamespace(cached_tokens=100),
            output_tokens_details=SimpleNamespace(reasoning_tokens=25),
        )
        return SimpleNamespace(
            id=f"resp-{len(self.calls)}",
            _request_id=f"req-{len(self.calls)}",
            output_parsed=output,
            usage=usage,
        )


class FakeAPIError(Exception):
    request_id = "req-failed"
    status_code = 500


class FakeSDK:
    def __init__(self, *, fail_on_synthesis: bool = False) -> None:
        self.responses = FakeResponses(fail_on_synthesis=fail_on_synthesis)


def write_article(path: Path, *, text: str = "published influential work") -> None:
    path.write_text(
        json.dumps(
            {
                "id": "ada",
                "title": "Ada Lovelace",
                "url": "https://example.test/ada",
                "text": text,
                "extra_source_field": {"preserved": True},
            }
        ),
        encoding="utf-8",
    )


def write_page_results(path: Path) -> None:
    pages = []
    for rank in (1, 2):
        pages.append(
            {
                "rank": rank,
                "discovery": {"method": "example"},
                "identity": {
                    "wiki": "enwiki",
                    "page_id": 100 + rank,
                    "title": f"Article {rank}",
                    "canonical_url": f"https://en.wikipedia.org/wiki/Article_{rank}",
                    "revision_id": 200 + rank,
                    "revision_timestamp": "2026-07-21T10:00:00Z",
                },
                "card": {
                    "description": None,
                    "wikidata_id": None,
                    "length_bytes": 123,
                    "last_touched": "2026-07-21T10:00:00Z",
                    "is_disambiguation": False,
                },
                "content": {"full_plain_text": "published influential work"},
            }
        )
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "example_id": "batch-example",
                "description": "Two page enrichment example",
                "retrieved_at": "2026-07-21T10:00:00Z",
                "wiki": "enwiki",
                "source": {
                    "endpoint": "https://en.wikipedia.org/w/api.php",
                    "parameters": {"action": "query"},
                },
                "expansion": {
                    "mode": "natural",
                    "anchor": None,
                    "shortfall": True,
                    "note": None,
                },
                "result_count": len(pages),
                "pages": pages,
            }
        ),
        encoding="utf-8",
    )


class EnrichmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = connect(":memory:")
        migrate(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_migration_constraints_and_costs(self) -> None:
        tables = {
            row["name"]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue(
            {
                "articles",
                "enrichment_runs",
                "article_analyses",
                "tags",
                "article_tags",
                "llm_calls",
                "profiles",
                "fictional_characters",
                "groups",
                "posts",
                "post_groups",
                "likes",
                "comments",
                "profile_group_follows",
            }
            <= tables
        )
        post_columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(posts)")
        }
        self.assertIn("article_id", post_columns)
        self.assertIn("enrichment_run_id", post_columns)
        self.assertEqual(
            estimate_cost("gpt-5.6-luna", Usage(1000, 100, 200, 25, 1200)),
            Decimal("0.002110000000"),
        )
        self.assertIsNone(
            estimate_cost("future-model", Usage(1, 0, 1, 0, 2))
        )
        long_cost = estimate_cost(
            "gpt-5.6-luna", Usage(300_000, 0, 1000, 0, 301_000)
        )
        self.assertEqual(long_cost, Decimal("0.609000000000"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO tags VALUES (1, 'topic', 'bad', 'Bad', 'not-json', 'now')"
            )
        dossier = ArticleDossier.model_validate(
            DOSSIER
            | {
                "key_facts": [
                    {
                        "id": "f1",
                        "claim": "She wrote notes.",
                        "evidence": "Lovelace’s notes",
                    }
                ]
            }
        )
        validate_dossier(dossier, "Lovelace's   notes became influential.")

    def test_observed_client_records_success_and_failure(self) -> None:
        with patch("openai.OpenAI") as sdk_constructor:
            OpenAIClient(self.connection, max_retries=4, timeout=90)
            sdk_constructor.assert_called_once_with(max_retries=4, timeout=90)

        sdk = FakeSDK()
        client = OpenAIClient(self.connection, sdk_client=sdk)
        result = client.parse(
            operation="test",
            model="gpt-5.6-luna",
            instructions="Return a number.",
            input="seven",
            output_type=TinyOutput,
            reasoning_effort="low",
            prompt_version="test-1",
        )
        self.assertEqual(result.output.value, 7)
        row = self.connection.execute("SELECT * FROM llm_calls").fetchone()
        self.assertEqual(row["status"], "succeeded")
        self.assertEqual(row["request_id"], "req-1")
        self.assertEqual(row["cached_input_tokens"], 100)
        self.assertEqual(row["estimated_cost_usd"], "0.002110000000")

        failing = OpenAIClient(
            self.connection, sdk_client=FakeSDK(fail_on_synthesis=True)
        )
        from app.enrichment import DiscoverySynthesis

        with self.assertRaises(FakeAPIError):
            failing.parse(
                operation="discovery_synthesis",
                model="unknown-model",
                instructions="test",
                input="test",
                output_type=DiscoverySynthesis,
                reasoning_effort="low",
                prompt_version="test-1",
            )
        failed = self.connection.execute(
            "SELECT * FROM llm_calls ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["request_id"], "req-failed")
        self.assertEqual(failed["status_code"], 500)

    def test_pipeline_persists_current_result_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            article_path = Path(directory) / "article.json"
            write_article(article_path)
            sdk = FakeSDK()
            pipeline = EnrichmentPipeline(
                self.connection,
                OpenAIClient(self.connection, sdk_client=sdk),
            )
            self.assertEqual(pipeline.process(article_path), "succeeded")
            self.assertEqual(pipeline.process(article_path), "skipped")
            self.assertEqual(len(sdk.responses.calls), 2)
            self.assertEqual(pipeline.process(article_path, force=True), "succeeded")
            self.assertEqual(len(sdk.responses.calls), 4)

        runs = self.connection.execute(
            "SELECT status, is_current FROM enrichment_runs ORDER BY id"
        ).fetchall()
        self.assertEqual(len(runs), 2)
        self.assertEqual(sum(row["is_current"] for row in runs), 1)
        current = self.connection.execute(
            "SELECT * FROM current_article_enrichments"
        ).fetchone()
        tags = json.loads(current["tags_json"])
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["slug"], "computing-history")
        self.assertIn('"extra_source_field"', current["raw_json"])

    def test_pass_one_survives_synthesis_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            article_path = Path(directory) / "article.json"
            write_article(article_path)
            good = EnrichmentPipeline(
                self.connection,
                OpenAIClient(self.connection, sdk_client=FakeSDK()),
            )
            good.process(article_path)
            write_article(article_path, text="published influential work, revised")
            failing = EnrichmentPipeline(
                self.connection,
                OpenAIClient(
                    self.connection,
                    sdk_client=FakeSDK(fail_on_synthesis=True),
                ),
            )
            with self.assertRaises(FakeAPIError):
                failing.process(article_path)

        failed = self.connection.execute(
            """
            SELECT r.status, a.extraction_json, a.synthesis_json
            FROM enrichment_runs AS r
            JOIN article_analyses AS a ON a.run_id = r.id
            ORDER BY r.id DESC LIMIT 1
            """
        ).fetchone()
        self.assertEqual(failed["status"], "failed")
        self.assertIsNotNone(failed["extraction_json"])
        self.assertIsNone(failed["synthesis_json"])
        self.assertIsNone(
            self.connection.execute(
                "SELECT 1 FROM current_article_enrichments"
            ).fetchone()
        )

    def test_directory_continues_after_invalid_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a-bad.json").write_text("[]", encoding="utf-8")
            write_article(root / "b-good.json")
            stats = run_directory(
                root,
                database_path=root / "test.db",
                sdk_client=FakeSDK(),
            )
        self.assertEqual(stats, {"succeeded": 1, "skipped": 0, "failed": 1})

    def test_directory_enriches_page_results_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_page_results(root / "page-results.json")
            database_path = root / "test.db"
            stats = run_directory(
                root,
                database_path=database_path,
                sdk_client=FakeSDK(),
            )
            repeated_stats = run_directory(
                root,
                database_path=database_path,
                sdk_client=FakeSDK(),
            )
            with closing(connect(database_path)) as connection:
                articles = connection.execute(
                    "SELECT id, language FROM articles ORDER BY id"
                ).fetchall()

        self.assertEqual(stats, {"succeeded": 2, "skipped": 0, "failed": 0})
        self.assertEqual(
            repeated_stats, {"succeeded": 0, "skipped": 2, "failed": 0}
        )
        self.assertEqual(
            [(row["id"], row["language"]) for row in articles],
            [("enwiki:101", "en"), ("enwiki:102", "en")],
        )

    def test_post_worker_creates_post_and_reuses_character(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "posts.db"
            article_path = root / "article.json"
            write_article(article_path)
            with closing(connect(database_path)) as connection:
                migrate(connection)
                EnrichmentPipeline(
                    connection,
                    OpenAIClient(connection, sdk_client=FakeSDK()),
                ).process(article_path)
                connection.execute(
                    """
                    INSERT INTO fictional_characters (id, name, description)
                    VALUES ('existing-ada', 'Ada Lovelace', 'Existing character')
                    """
                )
                connection.commit()

            self.assertEqual(
                generate_pending_posts(database_path, sdk_client=FakeSDK()),
                {"succeeded": 1, "skipped": 0, "failed": 0},
            )
            self.assertEqual(
                generate_pending_posts(database_path, sdk_client=FakeSDK()),
                {"succeeded": 0, "skipped": 0, "failed": 0},
            )
            with closing(connect(database_path)) as connection:
                post = connection.execute("SELECT * FROM posts").fetchone()
                self.assertEqual(post["fictional_character_id"], "existing-ada")
                self.assertEqual(post["article_id"], "ada")
                self.assertIsNotNone(post["enrichment_run_id"])
                self.assertEqual(json.loads(post["tags"]), ["computing-history"])
                self.assertIn("future", post["title"].lower())
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM fictional_characters"
                    ).fetchone()[0],
                    1,
                )
                call = connection.execute(
                    "SELECT operation, status FROM llm_calls ORDER BY id DESC LIMIT 1"
                ).fetchone()
                self.assertEqual(
                    (call["operation"], call["status"]),
                    ("post_generation", "succeeded"),
                )
                old_run_id = post["enrichment_run_id"]
                EnrichmentPipeline(
                    connection,
                    OpenAIClient(connection, sdk_client=FakeSDK()),
                ).process(article_path, force=True)
                self.assertEqual(
                    get_post_enrichment(connection, post["id"])["enrichment"][
                        "enrichment_run_id"
                    ],
                    old_run_id,
                )

    def test_enrichment_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "api.db"
            article_path = root / "article.json"
            write_article(article_path)
            with closing(connect(database_path)) as connection:
                migrate(connection)
                pipeline = EnrichmentPipeline(
                    connection,
                    OpenAIClient(connection, sdk_client=FakeSDK()),
                )
                pipeline.process(article_path)
                connection.execute(
                    "INSERT INTO fictional_characters (id, name) VALUES ('ada-character', 'Ada')"
                )
                connection.execute(
                    """
                    INSERT INTO posts (
                        id, fictional_character_id, title, content, content_type,
                        historical_start_year, historical_precision,
                        historical_date_label, article_id
                    ) VALUES (
                        'ada-post', 'ada-character', 'A post', 'Post body', 'text',
                        1843, 'year', '1843', 'ada'
                    )
                    """
                )
                connection.commit()

            api = FastAPI()
            api.include_router(enrichment_router)

            def database_override():
                with closing(connect(database_path)) as connection:
                    yield connection

            api.dependency_overrides[get_connection] = database_override
            with TestClient(api) as client:
                self.assertEqual(len(client.get("/enrichments").json()), 1)
                self.assertEqual(
                    client.get("/enrichments/ada").json()["article_id"], "ada"
                )
                self.assertEqual(client.get("/tags").json()[0]["article_count"], 1)
                self.assertEqual(
                    len(
                        client.get(
                            "/tags/topic/computing-history/enrichments"
                        ).json()
                    ),
                    1,
                )
                self.assertEqual(
                    client.get("/posts/ada-post/enrichment").json()["enrichment"][
                        "article_id"
                    ],
                    "ada",
                )
                self.assertEqual(client.get("/enrichments/missing").status_code, 404)
                self.assertEqual(client.get("/enrichments?limit=0").status_code, 422)


if __name__ == "__main__":
    unittest.main()
