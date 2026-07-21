import asyncio
import logging
from contextlib import asynccontextmanager, closing, suppress

from dotenv import load_dotenv
from fastapi import FastAPI

from .db import connect, migrate
from .enrichment_routes import router as enrichment_router
from .enrichment_watcher import configured_input_dir, watch_enrichment_directory
from .logger import configure_logging
from .post_generation import watch_enrichments_for_posts
from .router import router

load_dotenv()
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with closing(connect()) as connection:
        migrate(connection)
    tasks = [
        asyncio.create_task(watch_enrichment_directory(configured_input_dir())),
        asyncio.create_task(watch_enrichments_for_posts()),
    ]
    logger.info("API started")
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Wikipedia Doomscroll API", lifespan=lifespan)
app.include_router(router)
app.include_router(enrichment_router)
