"""SQLite-backed persistence for payments, jobs, and users."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


class Database:
    """Minimal SQLite wrapper for bot state."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS payments (
                    invoice_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    usd_amount REAL NOT NULL,
                    btc_amount REAL NOT NULL,
                    btc_address TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prompts TEXT,
                    output_paths TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def ensure_user(self, user_id: str, username: Optional[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username=excluded.username
                """,
                (user_id, username),
            )

    def record_payment(
        self,
        invoice_id: str,
        user_id: str,
        usd_amount: float,
        btc_amount: float,
        btc_address: str,
        status: str = "pending",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO payments
                (invoice_id, user_id, usd_amount, btc_amount, btc_address, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM payments WHERE invoice_id=?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)
                """,
                (
                    invoice_id,
                    user_id,
                    usd_amount,
                    btc_amount,
                    btc_address,
                    status,
                    invoice_id,
                ),
            )

    def update_payment_status(self, invoice_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE payments
                SET status=?, updated_at=?
                WHERE invoice_id=?
                """,
                (status, datetime.utcnow().isoformat(), invoice_id),
            )

    def get_payment(self, invoice_id: str) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM payments WHERE invoice_id=?
                """,
                (invoice_id,),
            )
            return cur.fetchone()

    def create_job(
        self,
        job_id: str,
        user_id: str,
        invoice_id: str,
        prompts: Iterable[str],
        status: str = "pending",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs
                (job_id, user_id, invoice_id, status, prompts, output_paths, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM jobs WHERE job_id=?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP)
                """,
                (
                    job_id,
                    user_id,
                    invoice_id,
                    status,
                    json.dumps(list(prompts)),
                    json.dumps([]),
                    job_id,
                ),
            )

    def update_job_status(
        self,
        job_id: str,
        status: str,
        output_paths: Optional[List[str]] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status=?, output_paths=?, updated_at=?
                WHERE job_id=?
                """,
                (
                    status,
                    json.dumps(output_paths or []),
                    datetime.utcnow().isoformat(),
                    job_id,
                ),
            )

    def get_job_by_invoice(self, invoice_id: str) -> Optional[sqlite3.Row]:
        """Get the most recent job for an invoice."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM jobs 
                WHERE invoice_id=?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (invoice_id,),
            )
            return cur.fetchone()





