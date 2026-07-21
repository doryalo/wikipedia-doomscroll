import asyncio
import logging
import os
from pathlib import Path

from watchfiles import Change, awatch

from .db import DATABASE_PATH
from .enrich import run_directory

logger = logging.getLogger(__name__)
BACKEND_PATH = Path(__file__).parent.parent
DEFAULT_INPUT_DIR = BACKEND_PATH / "data" / "raw-articles"


def configured_input_dir() -> Path:
    configured = Path(
        os.getenv("ENRICHMENT_INPUT_DIR", str(DEFAULT_INPUT_DIR))
    ).expanduser()
    return configured if configured.is_absolute() else BACKEND_PATH / configured


async def watch_enrichment_directory(
    input_dir: Path, *, database_path: Path = DATABASE_PATH
) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    await _scan(input_dir, database_path)
    async for changes in awatch(input_dir):
        if any(
            change in {Change.added, Change.modified, Change.deleted}
            and Path(changed_path).suffix.lower() == ".json"
            for change, changed_path in changes
        ):
            await _scan(input_dir, database_path)


async def _scan(input_dir: Path, database_path: Path) -> None:
    try:
        stats = await asyncio.to_thread(
            run_directory, input_dir, database_path=database_path
        )
        logger.info(
            "enrichment.scan path=%s succeeded=%s skipped=%s failed=%s",
            input_dir,
            stats["succeeded"],
            stats["skipped"],
            stats["failed"],
        )
    except Exception:
        logger.exception("enrichment.scan_failed path=%s", input_dir)
