import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "orders.db"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                amount_cdf INTEGER NOT NULL,
                phone TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                address TEXT NOT NULL,
                shwary_tx_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
                event_key TEXT PRIMARY KEY,
                shwary_tx_id TEXT NOT NULL,
                status TEXT NOT NULL,
                processed_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_phone_status
            ON orders (phone, status, created_at)
            """
        )


def create_order(product_id, product_name, amount_cdf, phone, customer_name, address):
    order_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO orders (
                id, product_id, product_name, amount_cdf,
                phone, customer_name, address, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                order_id,
                product_id,
                product_name,
                amount_cdf,
                phone,
                customer_name,
                address,
                now,
                now,
            ),
        )
    return order_id


def attach_shwary_transaction(order_id, shwary_tx_id):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE orders
            SET shwary_tx_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (shwary_tx_id, now, order_id),
        )


def update_order_status(order_id, status, expected_amount=None):
    with _connect() as conn:
        row = conn.execute(
            "SELECT amount_cdf, status FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if not row:
            return False
        if expected_amount is not None and int(row["amount_cdf"]) != int(expected_amount):
            return False
        if row["status"] == "paid" and status != "paid":
            return True
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            UPDATE orders SET status = ?, updated_at = ? WHERE id = ?
            """,
            (status, now, order_id),
        )
    return True


def get_order_by_id(order_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


def get_order_by_shwary_tx(shwary_tx_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE shwary_tx_id = ?", (shwary_tx_id,)
        ).fetchone()
    return dict(row) if row else None


def has_recent_pending_order(phone, product_id, minutes):
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM orders
            WHERE phone = ? AND product_id = ? AND status = 'pending'
            AND created_at > ?
            LIMIT 1
            """,
            (phone, product_id, cutoff),
        ).fetchone()
    return row is not None


def is_webhook_duplicate(event_key):
    with _connect() as conn:
        row = conn.execute(
            "SELECT event_key FROM webhook_events WHERE event_key = ?",
            (event_key,),
        ).fetchone()
    return row is not None


def record_webhook_event(event_key, shwary_tx_id, status):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO webhook_events (event_key, shwary_tx_id, status, processed_at)
            VALUES (?, ?, ?, ?)
            """,
            (event_key, shwary_tx_id, status, now),
        )
