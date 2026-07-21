import asyncio
import fcntl
import logging
from contextlib import asynccontextmanager, closing, suppress
from pathlib import Path
from typing import TextIO

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import DATABASE_PATH, connect, migrate
from .enrichment_routes import router as enrichment_router
from .enrichment_watcher import configured_input_dir, watch_enrichment_directory
from .logger import configure_logging
from .post_generation import watch_enrichments_for_posts
from .router import router

load_dotenv()
configure_logging()
logger = logging.getLogger(__name__)
BACKGROUND_WORKER_LOCK = DATABASE_PATH.parent / "background-workers.lock"


def _claim_background_workers(lock_path: Path = BACKGROUND_WORKER_LOCK) -> TextIO | None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = lock_path.open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return None
    return lock


@asynccontextmanager
async def lifespan(_: FastAPI):
    with closing(connect()) as connection:
        migrate(connection)
    # ponytail: one elected owner; use a durable queue for independent failover.
    worker_lock = _claim_background_workers()
    workers = (
        asyncio.gather(
            watch_enrichment_directory(configured_input_dir()),
            watch_enrichments_for_posts(),
        )
        if worker_lock
        else None
    )
    logger.info("API started background_workers=%s", bool(worker_lock))
    try:
        yield
    finally:
        if workers:
            workers.cancel()
            with suppress(asyncio.CancelledError):
                await workers
        if worker_lock:
            worker_lock.close()


app = FastAPI(title="Wikipedia Doomscroll API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(enrichment_router)
