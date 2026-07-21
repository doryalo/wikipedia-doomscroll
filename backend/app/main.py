import logging

from fastapi import FastAPI

from .logger import configure_logging
from .router import router

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Wikipedia Doomscroll API")
app.include_router(router)


@app.on_event("startup")
async def startup() -> None:
    logger.info("API started")

