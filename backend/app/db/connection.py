import os
import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional, Generator
from backend.app.core.config import settings

logger = logging.getLogger("sonovoice.db")

def configure_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    """
    Applies production SQLite pragmas:
    - Enforce foreign key constraints
    - Enable Write-Ahead Logging (WAL) for concurrency
    - Set busy timeout to prevent locking errors under load
    - Return rows as dictionary-like Row objects
    """
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Creates and returns a single configured SQLite connection.
    Caller is responsible for closing.
    """
    path = db_path or settings.DATABASE_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0, check_same_thread=False)
    return configure_connection(conn)

@contextmanager
def get_db(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Transactional context manager for database operations.
    Automatically commits on success and rolls back on exception.
    """
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        conn.close()

def get_db_dep() -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency that yields a managed database connection.
    """
    with get_db() as conn:
        yield conn
