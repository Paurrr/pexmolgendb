import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    if not path or str(path) in ("", ".") or not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
