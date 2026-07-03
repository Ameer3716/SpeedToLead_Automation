import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import os

import config

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            source TEXT,
            message TEXT,
            status TEXT DEFAULT 'New',
            created_at TIMESTAMP,
            response_time_seconds REAL,
            reminder_sent BOOLEAN DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            event_type TEXT,
            detail TEXT,
            created_at TIMESTAMP,
            FOREIGN KEY(lead_id) REFERENCES leads(id)
        )
    ''')
    conn.commit()
    conn.close()

def create_lead(name: str, email: Optional[str], phone: Optional[str], source: str, message: Optional[str], created_at: datetime) -> int:
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO leads (name, email, phone, source, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, email, phone, source, message, created_at.isoformat()))
    lead_id = c.lastrowid
    conn.commit()
    conn.close()

    add_event(lead_id, "lead_created", f"Lead arrived from {source}")
    return lead_id

def add_event(lead_id: int, event_type: str, detail: str):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO events (lead_id, event_type, detail, created_at)
        VALUES (?, ?, ?, ?)
    ''', (lead_id, event_type, detail, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

def mark_contacted(lead_id: int, response_time_seconds: float):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''
        UPDATE leads
        SET status = 'Contacted', response_time_seconds = ?
        WHERE id = ? AND status = 'New'
    ''', (response_time_seconds, lead_id))
    conn.commit()
    conn.close()

def update_status(lead_id: int, status: str):
    conn = _get_conn()
    c = conn.cursor()
    c.execute('''
        UPDATE leads
        SET status = ?
        WHERE id = ?
    ''', (status, lead_id))
    conn.commit()
    conn.close()

def needs_reminder(lead_id: int) -> bool:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT status, reminder_sent FROM leads WHERE id = ?", (lead_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row['status'] in ('New', 'Contacted') and not row['reminder_sent']
    return False

def mark_reminder_sent(lead_id: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("UPDATE leads SET reminder_sent = 1 WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()

def get_lead(lead_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def list_leads(status_filter: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    if status_filter:
        c.execute("SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status_filter, limit))
    else:
        c.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def list_events(lead_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    if lead_id:
        c.execute('''
            SELECT events.*, leads.name as lead_name
            FROM events
            LEFT JOIN leads ON events.lead_id = leads.id
            WHERE lead_id = ?
            ORDER BY events.created_at DESC LIMIT ?
        ''', (lead_id, limit))
    else:
        c.execute('''
            SELECT events.*, leads.name as lead_name
            FROM events
            LEFT JOIN leads ON events.lead_id = leads.id
            ORDER BY events.created_at DESC LIMIT ?
        ''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_stats() -> Dict[str, Any]:
    conn = _get_conn()
    c = conn.cursor()

    c.execute("SELECT count(*) as c FROM leads WHERE datetime(created_at) >= datetime('now', '-1 day')")
    last_24h = c.fetchone()['c']

    c.execute("SELECT count(*) as c FROM leads WHERE status = 'Booked'")
    booked = c.fetchone()['c']

    c.execute("SELECT count(*) as c FROM leads")
    total = c.fetchone()['c']

    conversion_rate = round((booked / total * 100), 1) if total > 0 else 0

    c.execute("SELECT count(*) as c FROM leads WHERE status IN ('New', 'Contacted')")
    pending = c.fetchone()['c']

    c.execute("SELECT avg(response_time_seconds) as a FROM leads WHERE response_time_seconds IS NOT NULL")
    avg_resp = c.fetchone()['a']

    speed_multiplier = round(config.INDUSTRY_AVERAGE_RESPONSE_SECONDS / avg_resp, 1) if avg_resp and avg_resp > 0 else 0

    conn.close()
    return {
        "leads_last_24h": last_24h,
        "booked": booked,
        "total": total,
        "conversion_rate": conversion_rate,
        "pending": pending,
        "avg_response_seconds": avg_resp,
        "speed_multiplier": speed_multiplier
    }

def reset_all():
    """Wipes every lead + event. Used by POST /admin/reset so you can clear
    fake demo leads before a live client call, or clear a client's data
    between trials without deleting the whole database file."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM events")
    c.execute("DELETE FROM leads")
    c.execute("DELETE FROM sqlite_sequence WHERE name IN ('leads', 'events')")
    conn.commit()
    conn.close()
