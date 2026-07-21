import sqlite3
from contextlib import closing
from pathlib import Path

DATABASE_PATH = Path(__file__).parent.parent / "data" / "app.db"


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def is_ready() -> bool:
    try:
        with closing(connect()) as connection:
            connection.execute("SELECT 1")
        return True
    except (OSError, sqlite3.Error):
        return False
