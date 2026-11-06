"""Flask extension singletons."""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record):
    """Enable foreign keys and WAL mode for SQLite connections.

    WAL lets the background simulator thread write readings while API requests
    read them without "database is locked" errors.
    """
    module = type(dbapi_connection).__module__
    if not module.startswith("sqlite3"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
    except Exception:  # in-memory databases do not support WAL
        pass
    cursor.close()

