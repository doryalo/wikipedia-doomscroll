import argparse
import logging
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv

from .db import DATABASE_PATH, connect, migrate
from .enrichment import EnrichmentPipeline
from .logger import configure_logging
from .openai_client import OpenAIClient

logger = logging.getLogger(__name__)


def run_directory(
    input_dir: Path,
    *,
    database_path: Path = DATABASE_PATH,
    force: bool = False,
    limit: int | None = None,
    sdk_client: object | None = None,
) -> dict[str, int]:
    if not input_dir.is_dir():
        raise ValueError(f"input directory does not exist: {input_dir}")
    files = sorted(input_dir.glob("*.json"))
    if limit is not None:
        files = files[:limit]
    stats = {"succeeded": 0, "skipped": 0, "failed": 0}
    if not files:
        return stats

    with closing(connect(database_path)) as connection:
        migrate(connection)
        pipeline = EnrichmentPipeline(
            connection,
            OpenAIClient(connection, sdk_client=sdk_client),
        )
        for path in files:
            try:
                file_stats = pipeline.process_file(path, force=force)
                if not file_stats["failed"]:
                    path.unlink()
                for status, count in file_stats.items():
                    stats[status] += count
            except Exception:
                stats["failed"] += 1
                logger.error("file.failed path=%s", path)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enrich Wikipedia article JSON files into SQLite"
    )
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--db", type=Path, default=DATABASE_PATH)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=_positive_int)
    args = parser.parse_args()
    load_dotenv()
    configure_logging()
    stats = run_directory(
        args.input_dir,
        database_path=args.db,
        force=args.force,
        limit=args.limit,
    )
    logger.info(
        "enrichment.summary succeeded=%s skipped=%s failed=%s",
        stats["succeeded"],
        stats["skipped"],
        stats["failed"],
    )
    return 1 if stats["failed"] else 0


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
