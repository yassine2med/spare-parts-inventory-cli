"""SQLite storage for spare parts and their movements."""
from __future__ import annotations

import csv
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS parts (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    min_qty INTEGER NOT NULL CHECK (min_qty >= 0),
    location TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL REFERENCES parts(sku),
    delta INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    at TEXT NOT NULL
);
"""


class StockError(Exception):
    """Raised for unknown parts, bad quantities or issuing more than is in stock."""


def connect(path: str) -> sqlite3.Connection:
    """Open the database (created if needed) and make sure the tables exist."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_part(conn: sqlite3.Connection, sku: str, name: str, quantity: int, min_qty: int, location: str = "") -> None:
    """Create a part. Raises StockError if the SKU exists or numbers are negative."""
    if quantity < 0 or min_qty < 0:
        raise StockError("quantity and min_qty cannot be negative")
    try:
        with conn:
            conn.execute("INSERT INTO parts VALUES (?, ?, ?, ?, ?)", (sku, name, quantity, min_qty, location))
            if quantity:
                _log(conn, sku, quantity, "initial stock")
    except sqlite3.IntegrityError:
        raise StockError(f"part {sku} already exists") from None


def _log(conn: sqlite3.Connection, sku: str, delta: int, note: str) -> None:
    conn.execute("INSERT INTO moves (sku, delta, note, at) VALUES (?, ?, ?, ?)",
                 (sku, delta, note, datetime.now().isoformat(timespec="seconds")))


def move(conn: sqlite3.Connection, sku: str, delta: int, note: str = "") -> int:
    """Change stock by delta (positive receive, negative issue). Returns the new quantity."""
    if delta == 0:
        raise StockError("quantity must not be zero")
    row = conn.execute("SELECT quantity FROM parts WHERE sku = ?", (sku,)).fetchone()
    if row is None:
        raise StockError(f"unknown part {sku}")
    new = row["quantity"] + delta
    if new < 0:
        raise StockError(f"only {row['quantity']} of {sku} in stock, cannot issue {-delta}")
    with conn:
        conn.execute("UPDATE parts SET quantity = ? WHERE sku = ?", (new, sku))
        _log(conn, sku, delta, note)
    return new


def low_stock(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Parts at or below their minimum, largest shortfall first."""
    return conn.execute(
        "SELECT *, min_qty - quantity AS short FROM parts WHERE quantity <= min_qty ORDER BY short DESC, sku"
    ).fetchall()


def all_parts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every part ordered by SKU."""
    return conn.execute("SELECT * FROM parts ORDER BY sku").fetchall()


def history(conn: sqlite3.Connection, sku: str) -> list[sqlite3.Row]:
    """Movements of one part, oldest first."""
    if conn.execute("SELECT 1 FROM parts WHERE sku = ?", (sku,)).fetchone() is None:
        raise StockError(f"unknown part {sku}")
    return conn.execute("SELECT * FROM moves WHERE sku = ? ORDER BY id", (sku,)).fetchall()


def import_csv(conn: sqlite3.Connection, path: str) -> int:
    """Add parts from a CSV (sku, name, quantity, min_qty, location). Returns how many were added."""
    count = 0
    with open(path, newline="", encoding="utf-8") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            try:
                add_part(conn, row["sku"], row["name"], int(row["quantity"]), int(row["min_qty"]), row.get("location", ""))
            except (KeyError, ValueError):
                raise StockError(f"{path} line {n}: missing or invalid value") from None
            count += 1
    return count
