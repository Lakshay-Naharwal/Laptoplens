"""
database/db.py
SQLite CRUD layer for price history and product metadata.
Designed to be swappable to PostgreSQL + TimescaleDB in production —
just swap sqlite3 for psycopg2 and update the SQL dialect.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Optional

# ─── Database path ────────────────────────────────────────────────────────────
# On HuggingFace Spaces, /data is the persistent volume.
# Locally, store next to this file.
_HF_DATA_DIR = Path("/data")
if _HF_DATA_DIR.exists():
    DB_PATH = str(_HF_DATA_DIR / "price_history.db")
else:
    DB_PATH = str(Path(__file__).parent.parent / "price_history.db")

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory for dict-like rows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent read performance
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Called once at app startup."""
    schema = _SCHEMA_PATH.read_text()
    with get_connection() as conn:
        conn.executescript(schema)
    print(f"[DB] Initialised at {DB_PATH}")


# ─── Product CRUD ─────────────────────────────────────────────────────────────

def upsert_product(
    product_id: str,
    name: str,
    image_url: str = "",
    buy_url: str = "",
    source: str = "mock",
    specs: Optional[dict] = None,
) -> None:
    """Insert a new product or update its metadata if it already exists."""
    specs_json = json.dumps(specs or {})
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO products (product_id, name, image_url, buy_url, source, specs_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                image_url    = excluded.image_url,
                buy_url      = excluded.buy_url,
                specs_json   = excluded.specs_json,
                last_updated = datetime('now', 'localtime')
            """,
            (product_id, name, image_url, buy_url, source, specs_json),
        )


def get_product(product_id: str) -> Optional[dict]:
    """Fetch product metadata by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
    if row:
        d = dict(row)
        d["specs"] = json.loads(d.pop("specs_json", "{}"))
        return d
    return None


# ─── Price History CRUD ───────────────────────────────────────────────────────

def insert_price(product_id: str, product_name: str, source: str, price: float) -> None:
    """
    Append a new price snapshot. NEVER overwrites existing records —
    this ensures we can reconstruct full price history.
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO price_history (product_id, product_name, source, price)
            VALUES (?, ?, ?, ?)
            """,
            (product_id, product_name, source, price),
        )


def get_price_history(product_id: str, days: int = 30) -> list[dict]:
    """
    Return price snapshots for a product over the last `days` days,
    ordered oldest → newest (for charting).
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT price, scraped_at
            FROM price_history
            WHERE product_id = ?
              AND scraped_at >= datetime('now', ?, 'localtime')
            ORDER BY scraped_at ASC
            """,
            (product_id, f"-{days} days"),
        ).fetchall()
    return [dict(r) for r in rows]


def get_price_stats(product_id: str, days: int = 30) -> dict:
    """
    Return min / max / avg / current price stats for a product.
    Returns empty dict if no history found yet.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                MIN(price)  AS min_price,
                MAX(price)  AS max_price,
                AVG(price)  AS avg_price,
                (SELECT price FROM price_history
                 WHERE product_id = ? ORDER BY scraped_at DESC LIMIT 1) AS current_price,
                COUNT(*)    AS data_points
            FROM price_history
            WHERE product_id = ?
              AND scraped_at >= datetime('now', ?, 'localtime')
            """,
            (product_id, product_id, f"-{days} days"),
        ).fetchone()

    if row and row["data_points"]:
        return {
            "min_price":     round(row["min_price"], 2),
            "max_price":     round(row["max_price"], 2),
            "avg_price":     round(row["avg_price"], 2),
            "current_price": round(row["current_price"], 2),
            "data_points":   row["data_points"],
        }
    return {}
