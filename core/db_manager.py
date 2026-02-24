"""SQLite DB 관리 — 스키마 + CRUD"""
import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict

from config import DB_PATH


def _ensure_dir():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_conn():
    """SQLite 커넥션 컨텍스트 매니저"""
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """DB 스키마 초기화"""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                target_type TEXT NOT NULL DEFAULT 'mall',
                target_value TEXT NOT NULL,
                sort_type TEXT NOT NULL DEFAULT 'sim',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS rank_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword_id INTEGER NOT NULL,
                rank INTEGER,
                title TEXT,
                mall_name TEXT,
                price INTEGER,
                link TEXT,
                product_id TEXT,
                checked_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS alert_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT,
                sent_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_rank_history_keyword
                ON rank_history(keyword_id, checked_at);
            CREATE INDEX IF NOT EXISTS idx_rank_history_checked
                ON rank_history(checked_at);
        """)


# ── Keywords CRUD ──

def add_keyword(keyword: str, target_type: str, target_value: str, sort_type: str = "sim") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO keywords (keyword, target_type, target_value, sort_type) VALUES (?, ?, ?, ?)",
            (keyword, target_type, target_value, sort_type),
        )
        return cur.lastrowid


def get_keywords(active_only: bool = False) -> List[Dict]:
    with get_conn() as conn:
        sql = "SELECT * FROM keywords"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY id"
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def update_keyword(keyword_id: int, **fields):
    allowed = {"keyword", "target_type", "target_value", "sort_type", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [keyword_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE keywords SET {set_clause} WHERE id = ?", values)


def delete_keyword(keyword_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))


# ── Rank History CRUD ──

def add_rank_record(keyword_id: int, rank: Optional[int] = None, title: str = None,
                    mall_name: str = None, price: int = None,
                    link: str = None, product_id: str = None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO rank_history
               (keyword_id, rank, title, mall_name, price, link, product_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (keyword_id, rank, title, mall_name, price, link, product_id),
        )


def get_latest_ranks() -> List[Dict]:
    """각 키워드의 최신 순위 조회"""
    sql = """
        SELECT k.id as keyword_id, k.keyword, k.target_type, k.target_value,
               k.sort_type, k.is_active,
               rh.rank, rh.title, rh.mall_name, rh.price, rh.link, rh.checked_at,
               prev.rank as prev_rank
        FROM keywords k
        LEFT JOIN rank_history rh ON rh.id = (
            SELECT id FROM rank_history
            WHERE keyword_id = k.id
            ORDER BY checked_at DESC LIMIT 1
        )
        LEFT JOIN rank_history prev ON prev.id = (
            SELECT id FROM rank_history
            WHERE keyword_id = k.id
            ORDER BY checked_at DESC LIMIT 1 OFFSET 1
        )
        WHERE k.is_active = 1
        ORDER BY k.id
    """
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def get_rank_history(keyword_id: int, days: int = 30) -> List[Dict]:
    sql = """
        SELECT * FROM rank_history
        WHERE keyword_id = ?
          AND checked_at >= datetime('now', 'localtime', ?)
        ORDER BY checked_at ASC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (keyword_id, f"-{days} days")).fetchall()
        return [dict(r) for r in rows]


def get_all_rank_history(days: int = 30) -> List[Dict]:
    sql = """
        SELECT rh.*, k.keyword, k.target_value
        FROM rank_history rh
        JOIN keywords k ON k.id = rh.keyword_id
        WHERE rh.checked_at >= datetime('now', 'localtime', ?)
        ORDER BY rh.checked_at ASC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (f"-{days} days",)).fetchall()
        return [dict(r) for r in rows]


# ── Alert Logs ──

def add_alert_log(keyword_id: int, alert_type: str, message: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO alert_logs (keyword_id, alert_type, message) VALUES (?, ?, ?)",
            (keyword_id, alert_type, message),
        )


def get_alert_logs(limit: int = 50) -> List[Dict]:
    sql = """
        SELECT al.*, k.keyword
        FROM alert_logs al
        JOIN keywords k ON k.id = al.keyword_id
        ORDER BY al.sent_at DESC LIMIT ?
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
        return [dict(r) for r in rows]


# ── Settings ──

def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value),
        )


def get_all_settings() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
