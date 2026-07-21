import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

DATABASE_PATH = Path(__file__).parent.parent / "data" / "app.db"
MIGRATIONS_PATH = Path(__file__).parent.parent / "migrations"


def connect(path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def new_id() -> str:
    return str(uuid.uuid4())


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {
        row["version"]
        for row in connection.execute("SELECT version FROM schema_migrations")
    }
    for migration in sorted(MIGRATIONS_PATH.glob("*.sql")):
        version = int(migration.stem.split("_", 1)[0])
        if version in applied:
            continue
        sql = migration.read_text(encoding="utf-8")
        try:
            connection.executescript(
                f"BEGIN IMMEDIATE;\n{sql}\n"
                f"INSERT INTO schema_migrations VALUES ({version}, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));\n"
                "COMMIT;"
            )
        except sqlite3.Error:
            connection.rollback()
            raise


def is_ready() -> bool:
    try:
        with closing(connect()) as connection:
            connection.execute("SELECT 1")
        return True
    except (OSError, sqlite3.Error):
        return False
