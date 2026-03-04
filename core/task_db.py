import sqlite3
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "openclaw.db"

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # access columns by name
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    """Create the tasks table if it doesn't exist."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL,
            category        TEXT DEFAULT 'uncategorized',
            priority        TEXT DEFAULT 'medium'
                            CHECK (priority IN ('high', 'medium', 'low')),
            due_date        DATE,
            estimated_minutes INTEGER,
            status          TEXT DEFAULT 'pending'
                            CHECK (status IN ('pending', 'in_progress', 'complete')),
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at    DATETIME,
            source          TEXT DEFAULT 'discord',
            notes           TEXT
        )
    """)
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def add_task(title, category="uncategorized", priority="medium",
             due_date=None, estimated_minutes=None, source="discord", notes=None):
    """Insert a single task. Returns the new row as a dict."""
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO tasks (title, category, priority, due_date,
                           estimated_minutes, source, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, category, priority, due_date, estimated_minutes, source, notes))
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

def add_tasks_bulk(task_list):
    """Insert multiple tasks from a list of dicts. Returns all new rows."""
    conn = get_conn()
    ids = []
    for t in task_list:
        cur = conn.execute("""
            INSERT INTO tasks (title, category, priority, due_date,
                               estimated_minutes, source, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            t["title"], t.get("category", "uncategorized"),
            t.get("priority", "medium"), t.get("due_date"),
            t.get("estimated_minutes"), t.get("source", "bulk"),
            t.get("notes")
        ))
        ids.append(cur.lastrowid)
    conn.commit()
    rows = conn.execute(
        f"SELECT * FROM tasks WHERE id IN ({','.join('?' * len(ids))})", ids
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def get_pending(category=None, include_past=False):
    """All pending/in_progress tasks, optionally filtered by category.
    By default hides tasks with due dates that have already passed."""
    conn = get_conn()
    q = "SELECT * FROM tasks WHERE status != 'complete'"
    params = []
    if not include_past:
        q += " AND (due_date IS NULL OR due_date >= date('now'))"
    if category:
        q += " AND category = ?"
        params.append(category)
    q += " ORDER BY due_date IS NULL, due_date ASC, priority = 'high' DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_due_within(days=1):
    """Tasks due within the next N days (for daily briefing)."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM tasks
        WHERE status != 'complete'
          AND due_date IS NOT NULL
          AND due_date <= date('now', ? || ' days')
        ORDER BY due_date ASC,
                 CASE priority WHEN 'high' THEN 0
                                WHEN 'medium' THEN 1
                                ELSE 2 END
    """, (str(days),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_completed():
    """All completed tasks, most recent first."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM tasks WHERE status = 'complete'
        ORDER BY completed_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_task(task_id):
    """Single task by ID."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
EDITABLE_FIELDS = {"title", "category", "priority", "due_date",
                   "estimated_minutes", "status", "notes"}

def edit_task(task_id, **fields):
    """Update one or more fields on a task. Returns updated row or None."""
    valid = {k: v for k, v in fields.items() if k in EDITABLE_FIELDS}
    if not valid:
        return None
    conn = get_conn()
    sets = ", ".join(f"{k} = ?" for k in valid)
    vals = list(valid.values()) + [task_id]
    conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", vals)
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def complete_task(task_id):
    """Mark a task as complete with a timestamp."""
    conn = get_conn()
    conn.execute("""
        UPDATE tasks SET status = 'complete', completed_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), task_id))
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
def delete_task(task_id):
    """Delete a task. Returns True if a row was removed."""
    conn = get_conn()
    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0

# ---------------------------------------------------------------------------
# Auto-init on import
# ---------------------------------------------------------------------------
init_db()