"""SQLite storage for CounterFlow."""
import os
import sqlite3
from contextlib import contextmanager

PATH = os.environ.get("COUNTERFLOW_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "counterflow.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT, service TEXT NOT NULL,
  cancelled INTEGER DEFAULT 0, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL REFERENCES requests(id),
  version_no INTEGER NOT NULL, fields TEXT NOT NULL, author TEXT NOT NULL,
  note TEXT DEFAULT '', created REAL, UNIQUE(request_id, version_no));
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL REFERENCES requests(id),
  sender TEXT NOT NULL, text TEXT NOT NULL, sign TEXT DEFAULT '', version_no INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS confirmations(
  request_id INTEGER NOT NULL, version_no INTEGER NOT NULL, role TEXT NOT NULL, created REAL,
  PRIMARY KEY(request_id, version_no, role));
"""


@contextmanager
def session():
    c = sqlite3.connect(PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init():
    with session() as c:
        c.executescript(SCHEMA)
