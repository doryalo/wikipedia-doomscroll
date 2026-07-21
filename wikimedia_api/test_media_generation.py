from __future__ import annotations

import tempfile
import unittest
from base64 import b64encode
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from wikimedia_api import main
from wikimedia_api.main import (
    MediaGenerationRequest,
    compose_media_prompt,
    write_media_record,
)


class MediaStorageTests(unittest.TestCase):
    def test_media_record_is_post_scoped_and_has_a_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            record = write_media_record(
                directory=directory,
                post_id="post-42",
                media_id="a" * 32,
                kind="image",
                extension="png",
                content=b"png-bytes",
                metadata={"status": "completed", "model": "gpt-image-2"},
            )

            self.assertEqual(
                record.artifact_path,
                directory / "post-42" / f"{'a' * 32}.png",
            )
            self.assertEqual(record.artifact_path.read_bytes(), b"png-bytes")
            self.assertEqual(record.sidecar_path.name, f"{'a' * 32}.json")
            self.assertIn('"post_id": "post-42"', record.sidecar_path.read_text())

    def test_prompt_labels_every_semantic_input(self) -> None:
        request = MediaGenerationRequest(
            postId="post-42",
            description="A telescope on a hill",
            logicalValue="Observation changes scientific understanding",
            timeFrame="1609",
            concept="A threshold to discovery",
            intent="Make viewers curious about astronomy",
        )

        prompt = compose_media_prompt(request, medium="still image")

        for label in (
            "Description:",
            "Logical value:",
            "Time frame:",
            "Concept:",
            "Intent:",
        ):
            self.assertIn(label, prompt)


class FakeImages:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return type(
            "ImageResponse",
            (),
            {"data": [type("GeneratedImage", (), {"b64_json": b64encode(b"image-bytes").decode()})()]},
        )()


class FakeOpenAI:
    def __init__(self, **_: object) -> None:
        self.images = FakeImages()

    async def close(self) -> None:
        return None


class FakeVideos:
    async def create(self, **_: object) -> object:
        return type(
            "QueuedVideo",
            (),
            {"id": "video-provider-1", "status": "queued", "model": "sora-2", "progress": 0},
        )()

    async def retrieve(self, _: str) -> object:
        return type(
            "CompletedVideo",
            (),
            {"id": "video-provider-1", "status": "completed", "model": "sora-2", "progress": 100},
        )()

    async def download_content(self, _: str) -> bytes:
        return b"mp4-bytes"


class FakeOpenAIWithVideos(FakeOpenAI):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.videos = FakeVideos()


class MediaEndpointTests(unittest.TestCase):
    def test_image_generation_persists_a_png_and_returns_post_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.object(main, "AsyncOpenAI", FakeOpenAI):
                with patch.object(main, "CONTACT", "tests@example.com"):
                    with patch.dict(main.os.environ, {"OPENAI_API_KEY": "test-key"}):
                        main.app.state.media_dir = Path(temporary_directory)
                        with TestClient(main.app) as client:
                            response = client.post(
                                "/v1/media/images/generations",
                                json={
                                    "postId": "post-42",
                                    "description": "A sundial",
                                    "logicalValue": "Time can be measured",
                                    "timeFrame": "Ancient Rome",
                                    "concept": "Light marks time",
                                    "intent": "Teach the idea simply",
                                },
                            )

            self.assertEqual(response.status_code, 201)
            body = response.json()
            self.assertEqual(body["postId"], "post-42")
            self.assertEqual(body["kind"], "image")
            self.assertEqual(body["status"], "completed")
            self.assertEqual(
                (Path(temporary_directory) / "post-42" / f'{body["mediaId"]}.png').read_bytes(),
                b"image-bytes",
            )

    def test_reel_status_persists_completed_mp4_and_serves_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.object(main, "AsyncOpenAI", FakeOpenAIWithVideos):
                with patch.object(main, "CONTACT", "tests@example.com"):
                    with patch.dict(main.os.environ, {"OPENAI_API_KEY": "test-key"}):
                        main.app.state.media_dir = Path(temporary_directory)
                        with TestClient(main.app) as client:
                            created = client.post(
                                "/v1/media/reels/generations",
                                json={
                                    "postId": "post-42",
                                    "description": "A ziggurat at dawn",
                                    "logicalValue": "Cities organized religious and civic life",
                                    "timeFrame": "2100 BCE",
                                    "concept": "A city rising around its temple",
                                    "intent": "Make viewers curious about Mesopotamia",
                                },
                            )
                            self.assertEqual(created.status_code, 202)
                            created_body = created.json()
                            self.assertEqual(created_body["status"], "queued")
                            self.assertEqual(created_body["providerJobId"], "video-provider-1")

                            status = client.get(created_body["statusUrl"])
                            artifact = client.get(created_body["artifactUrl"])

            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["status"], "completed")
            self.assertEqual(artifact.status_code, 200)
            self.assertEqual(artifact.content, b"mp4-bytes")
            self.assertTrue(artifact.headers["content-type"].startswith("video/mp4"))


class WikimediaAdapterRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_hydrate_fetches_revisions_per_page_not_in_batched_metadata(self) -> None:
        calls: list[dict[str, object]] = []

        async def fake_upstream(_: object, __: str, params: dict[str, object]) -> dict[str, object]:
            calls.append(params)
            if params.get("prop") == "info|pageterms|pageprops":
                return {
                    "query": {
                        "pages": [
                            {
                                "pageid": 1,
                                "title": "Sumer",
                                "canonicalurl": "https://en.wikipedia.org/wiki/Sumer",
                                "length": 100,
                                "touched": "2026-07-21T00:00:00Z",
                                "terms": {"description": ["ancient civilization"]},
                                "pageprops": {},
                            },
                            {
                                "pageid": 2,
                                "title": "Akkad",
                                "canonicalurl": "https://en.wikipedia.org/wiki/Akkad",
                                "length": 200,
                                "touched": "2026-07-21T00:00:00Z",
                                "terms": {"description": ["ancient city"]},
                                "pageprops": {},
                            },
                        ]
                    }
                }
            title = str(params["titles"])
            return {
                "query": {
                    "pages": [
                        {
                            "pageid": 1 if title == "Sumer" else 2,
                            "title": title,
                            "extract": f"{title} historical text",
                            "revisions": [{"revid": 10, "timestamp": "2026-07-21T00:00:00Z"}],
                        }
                    ]
                }
            }

        with patch.object(main, "upstream_json", fake_upstream):
            with patch.object(main, "write_raw_article"):
                result = await main.hydrate(
                    SimpleNamespace(),
                    ["Sumer", "Akkad"],
                    example_id="mesopotamia",
                    description="Mesopotamia",
                    endpoint="https://en.wikipedia.org/w/api.php",
                    parameters={},
                )

        self.assertEqual(result.status, "stored")
        self.assertNotIn("rvlimit", calls[0])
        self.assertEqual(calls[0]["prop"], "info|pageterms|pageprops")
        self.assertEqual(calls[1]["prop"], "extracts|revisions")


if __name__ == "__main__":
    unittest.main()
