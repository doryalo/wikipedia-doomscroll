import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import initialize
from .logger import configure_logging
from .router import router
from .seed import seed_demo_data

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Wikipedia Doomscroll API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
async def startup() -> None:
    initialize()
    seed_demo_data()
    logger.info("API started")
