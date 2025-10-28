"""Schema meta assertions: indices and PRAGMA user_version.
"""

import sqlite3


def test_schema_meta_smoke(manager):
    con = sqlite3.connect(manager.playtime_tracker.db_path)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indices = {r[0] for r in cur.fetchall()}
    assert "idx_sessions_bottle_program" in indices
    assert "idx_sessions_status" in indices
    assert "idx_totals_last_played" in indices
    cur.execute("PRAGMA user_version")
    assert cur.fetchone()[0] == 1
