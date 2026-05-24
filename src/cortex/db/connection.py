"""pyodbc connection management. All DB access goes through get_connection()."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Generator

import pyodbc
import structlog

from cortex.config import get_settings

log = structlog.get_logger(__name__)

_local = threading.local()


def get_connection() -> pyodbc.Connection:
    """Return a thread-local pyodbc connection, creating one if needed."""
    if not getattr(_local, "conn", None) or _local.conn.closed:
        settings = get_settings()
        _local.conn = pyodbc.connect(settings.db_connection_string, autocommit=False)
        # NVARCHAR/NCHAR (SQL_WCHAR) come off the wire as UTF-16LE. Decoding
        # them as UTF-8 (the previous setting) truncated multi-byte sequences
        # like em-dash (0xe2 0x80 0x94) at read-buffer boundaries — e.g. a
        # LEFT(body,800) preview ending mid-char threw UnicodeDecodeError.
        # VARCHAR/CHAR (SQL_CHAR) stay UTF-8.
        _local.conn.setdecoding(pyodbc.SQL_CHAR, encoding="utf-8")
        _local.conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16le")
        _local.conn.setencoding(encoding="utf-8")
        log.debug("db.connected", server=settings.db_server, database=settings.db_database)
    return _local.conn


@contextmanager
def transaction() -> Generator[pyodbc.Connection, None, None]:
    """Context manager that commits on success and rolls back on exception."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_connection() -> None:
    """Close the thread-local connection if open."""
    conn = getattr(_local, "conn", None)
    if conn and not conn.closed:
        conn.close()
        _local.conn = None
