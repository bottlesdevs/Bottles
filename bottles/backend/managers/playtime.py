# playtime.py
#
# Core playtime tracking manager: session lifecycle, heartbeats, recovery, and totals.

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger


logging = Logger()


SCHEMA_USER_VERSION = 1


@dataclass(frozen=True)
class _TrackedSession:
    session_id: int
    bottle_id: str
    program_id: str
    program_name: str
    started_at: int
    last_seen: int


def _utc_now_seconds() -> int:
    return int(time.time())


def _compute_program_id(bottle_id: str, program_path: str) -> str:
    normalized = f"{bottle_id}:{program_path}".encode("utf-8")
    return hashlib.sha1(normalized).hexdigest()


class ProcessSessionTracker:
    """
    Track program play sessions and maintain aggregated totals.

    This manager is self-contained and thread-safe for its public API. It
    opens a single SQLite connection with WAL enabled and performs batched
    heartbeat updates on a background thread.
    """

    def __init__(
        self,
        *,
        db_path: Optional[str] = None,
        heartbeat_interval: int = 60,
        enabled: bool = True,
    ) -> None:
        self.db_path = db_path or Paths.process_metrics
        self.heartbeat_interval = max(1, int(heartbeat_interval))
        self.enabled = bool(enabled)

        self._conn = self._connect()
        self._ensure_schema()

        self._lock = threading.RLock()
        self._tracked: Dict[int, _TrackedSession] = {}

        self._stop_event = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name="PlaytimeHeartbeat", daemon=True
        )
        if self.enabled:
            self._heartbeat_thread.start()

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=3000;")
        return conn

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bottle_id TEXT NOT NULL,
                bottle_name TEXT NOT NULL,
                bottle_path TEXT NOT NULL,
                program_id TEXT NOT NULL,
                program_name TEXT NOT NULL,
                program_path TEXT NOT NULL,
                started_at INTEGER NOT NULL,
                ended_at INTEGER,
                last_seen INTEGER NOT NULL,
                duration_seconds INTEGER,
                status TEXT NOT NULL CHECK (status IN ('running','success','crash','forced','unknown')),
                UNIQUE (bottle_id, program_id, started_at)
            );
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_bottle_program
            ON sessions (bottle_id, program_id);
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_status
            ON sessions (status);
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS playtime_totals (
                bottle_id TEXT NOT NULL,
                bottle_name TEXT NOT NULL,
                program_id TEXT NOT NULL,
                program_name TEXT NOT NULL,
                program_path TEXT NOT NULL,
                total_seconds INTEGER NOT NULL DEFAULT 0,
                sessions_count INTEGER NOT NULL DEFAULT 0,
                last_played INTEGER,
                PRIMARY KEY (bottle_id, program_id)
            );
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_totals_last_played
            ON playtime_totals (last_played DESC);
            """
        )

        cur.execute(f"PRAGMA user_version={SCHEMA_USER_VERSION};")
        self._conn.commit()

    def disable_tracking(self) -> None:
        self.enabled = False
        self.shutdown()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=self.heartbeat_interval + 1)
        with self._lock:
            self._tracked.clear()
        try:
            self._conn.commit()
            self._conn.close()
        except Exception:
            pass

    # Public API
    def start_session(
        self,
        *,
        bottle_id: str,
        bottle_name: str,
        bottle_path: str,
        program_name: str,
        program_path: str,
    ) -> int:
        if not self.enabled:
            logging.warning("Playtime tracking disabled; start_session is a no-op")
            return -1

        program_id = _compute_program_id(bottle_id, program_path)
        base_timestamp = _utc_now_seconds()

        with self._lock:
            cur = self._conn.cursor()

            # Collapse duplicates: if there is already a running session for this
            # (bottle_id, program_id), return its session_id instead of creating
            # a new one. Also ensure it is registered in the in-memory map.
            cur.execute(
                """
                SELECT id, started_at, last_seen, program_name
                FROM sessions
                WHERE bottle_id=? AND program_id=? AND status='running'
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (bottle_id, program_id),
            )
            existing = cur.fetchone()
            if existing is not None:
                existing_id = int(existing[0])
                existing_started_at = int(existing[1])
                existing_last_seen = int(existing[2])
                existing_program_name = str(existing[3])

                if existing_id not in self._tracked:
                    self._tracked[existing_id] = _TrackedSession(
                        session_id=existing_id,
                        bottle_id=bottle_id,
                        program_id=program_id,
                        program_name=existing_program_name,
                        started_at=existing_started_at,
                        last_seen=existing_last_seen,
                    )
                logging.info(
                    f"Session already running: id={existing_id} bottle={bottle_name} program={existing_program_name}"
                )
                return existing_id

            # Rarely, a restart within the same second can reuse the previous timestamp
            # (schema has a UNIQUE constraint on bottle/program/started_at). We bump the
            # timestamp deterministically to avoid throwing IntegrityError.
            retries = 0
            while True:
                started_at = base_timestamp + retries
                try:
                    cur.execute(
                        """
                        INSERT INTO sessions (
                            bottle_id, bottle_name, bottle_path,
                            program_id, program_name, program_path,
                            started_at, ended_at, last_seen, duration_seconds,
                            status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, 'running');
                        """,
                        (
                            bottle_id,
                            bottle_name,
                            bottle_path,
                            program_id,
                            program_name,
                            program_path,
                            started_at,
                            started_at,
                        ),
                    )
                    break
                except sqlite3.IntegrityError as exc:
                    if "UNIQUE constraint failed: sessions.bottle_id, sessions.program_id, sessions.started_at" not in str(exc):
                        raise
                    retries += 1
                    if retries > 5:
                        raise

            session_id = int(cur.lastrowid)
            self._conn.commit()

            # Track in-memory after successful commit
            self._tracked[session_id] = _TrackedSession(
                session_id=session_id,
                bottle_id=bottle_id,
                program_id=program_id,
                program_name=program_name,
                started_at=started_at,
                last_seen=started_at,
            )
        logging.info(
            f"Session started: id={session_id} bottle={bottle_name} program={program_name}"
        )
        return session_id

    def mark_exit(
        self,
        session_id: int,
        *,
        status: str = "success",
        ended_at: Optional[int] = None,
    ) -> None:
        if not self.enabled or session_id < 0:
            return

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT started_at, last_seen, bottle_id, program_id FROM sessions WHERE id=?",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                logging.error(f"mark_exit: session {session_id} not found")
                return
            started_at = int(row[0])
            last_seen = int(row[1])
            bottle_id = str(row[2])
            program_id = str(row[3])

            end_ts = int(ended_at) if ended_at is not None else _utc_now_seconds()
            duration = max(0, end_ts - started_at)

            # Finalize session and update totals atomically
            cur.execute(
                """
                UPDATE sessions
                SET ended_at=?, last_seen=?, duration_seconds=?, status=?
                WHERE id=?
                """,
                (end_ts, end_ts, duration, status, session_id),
            )

            logging.debug(
                f"Playtime finalize: id={session_id} bottle_id={bottle_id} program_id={program_id} "
                f"status={status} duration={duration}s ended_at={end_ts}"
            )

            self._tracked.pop(session_id, None)

            self._update_totals(bottle_id=bottle_id, program_id=program_id, cur=cur)
            self._conn.commit()

    def mark_failure(self, session_id: int, *, status: str) -> None:
        if status not in ("crash", "forced", "unknown"):
            status = "unknown"
        logging.debug(f"Playtime failure: id={session_id} status={status}")
        self.mark_exit(session_id, status=status)

    def recover_open_sessions(self) -> None:
        if not self.enabled:
            return
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, started_at, last_seen, bottle_id, program_id FROM sessions WHERE status='running'"
        )
        rows = cur.fetchall()
        if not rows:
            return

        now = _utc_now_seconds()
        with self._lock:
            for (sid, started_at, last_seen, bottle_id, program_id) in rows:
                end_ts = int(last_seen)
                duration = max(0, end_ts - int(started_at))
                cur.execute(
                    """
                    UPDATE sessions
                    SET ended_at=?, duration_seconds=?, status='forced'
                    WHERE id=?
                    """,
                    (end_ts, duration, sid),
                )
                self._tracked.pop(int(sid), None)
                self._update_totals(
                    bottle_id=str(bottle_id), program_id=str(program_id), cur=cur
                )
        self._conn.commit()
        logging.info(f"Recovered {len(rows)} running sessions -> forced at last_seen")

    # Internals
    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self.heartbeat_interval):
            try:
                self._flush_heartbeats()
            except Exception as e:
                logging.exception(e)

    def _flush_heartbeats(self) -> None:
        with self._lock:
            if not self._tracked:
                return
            now = _utc_now_seconds()
            cur = self._conn.cursor()
            for ts in self._tracked.values():
                cur.execute(
                    "UPDATE sessions SET last_seen=? WHERE id=? AND status='running'",
                    (now, ts.session_id),
                )
                # update in-memory copy
                self._tracked[ts.session_id] = _TrackedSession(
                    session_id=ts.session_id,
                    bottle_id=ts.bottle_id,
                    program_id=ts.program_id,
                    program_name=ts.program_name,
                    started_at=ts.started_at,
                    last_seen=now,
                )
                logging.debug(
                    f"Playtime heartbeat: id={ts.session_id} bottle_id={ts.bottle_id} "
                    f"program_id={ts.program_id} last_seen={now}"
                )
            self._conn.commit()

    def _update_totals(self, *, bottle_id: str, program_id: str, cur: Optional[sqlite3.Cursor] = None) -> None:
        cur = cur or self._conn.cursor()
        # Compute aggregate for this program from sessions that are not running
        cur.execute(
            """
            SELECT
              MAX(bottle_name),
              MAX(program_name),
              MAX(program_path),
              COALESCE(SUM(duration_seconds), 0),
              COUNT(*),
              MAX(COALESCE(ended_at, last_seen))
            FROM sessions
            WHERE bottle_id=? AND program_id=? AND status != 'running'
            """,
            (bottle_id, program_id),
        )
        row = cur.fetchone()
        if not row:
            return
        bottle_name, program_name, program_path, total_seconds, sessions_count, last_played = row

        cur.execute(
            """
            INSERT INTO playtime_totals (
              bottle_id, bottle_name, program_id, program_name, program_path,
              total_seconds, sessions_count, last_played
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bottle_id, program_id) DO UPDATE SET
              bottle_name=excluded.bottle_name,
              program_name=excluded.program_name,
              program_path=excluded.program_path,
              total_seconds=excluded.total_seconds,
              sessions_count=excluded.sessions_count,
              last_played=excluded.last_played
            """,
            (
                bottle_id,
                bottle_name,
                program_id,
                program_name,
                program_path,
                int(total_seconds or 0),
                int(sessions_count or 0),
                int(last_played or 0) if last_played is not None else None,
            ),
        )
        logging.debug(
            f"Playtime totals: bottle_id={bottle_id} program_id={program_id} "
            f"program_name={program_name} sessions_count={int(sessions_count or 0)} "
            f"total_seconds={int(total_seconds or 0)} last_played={int(last_played or 0) if last_played is not None else None}"
        )
        # Do not commit here; caller manages transaction boundaries


