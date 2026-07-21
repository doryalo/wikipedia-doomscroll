import logging
from contextlib import closing

from dotenv import load_dotenv
from fastapi import FastAPI

from .db import connect, migrate
from .logger import configure_logging
from .router import router

load_dotenv()
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Wikipedia Doomscroll API")
app.include_router(router)


@app.on_event("startup")
async def startup() -> None:
    with closing(connect()) as connection:
        migrate(connection)
    logger.info("API started")
