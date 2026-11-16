import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "patients.db"

FIELDS = ["full_name", "dob", "email", "glucose", "haemoglobin", "cholesterol", "remarks"]


class DuplicateEmail(Exception):
    pass


@contextmanager
def connect():
    # sqlite3's own context manager commits but never closes, so wrap it.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name   TEXT NOT NULL,
                dob         TEXT NOT NULL,
                email       TEXT NOT NULL UNIQUE COLLATE NOCASE,
                glucose     REAL NOT NULL,
                haemoglobin REAL NOT NULL,
                cholesterol REAL NOT NULL,
                remarks     TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def list_patients():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM patients ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_patient(patient_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return dict(row) if row else None


def email_taken(email, exclude_id=None):
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM patients WHERE email = ? AND id IS NOT ?",
            (email, exclude_id),
        ).fetchone()
    return row is not None


def add_patient(data):
    values = [data[f] for f in FIELDS]
    try:
        with connect() as conn:
            cur = conn.execute(
                f"INSERT INTO patients ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})",
                values,
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        raise DuplicateEmail(data["email"])


def update_patient(patient_id, data):
    assignments = ", ".join(f"{f} = ?" for f in FIELDS)
    try:
        with connect() as conn:
            conn.execute(
                f"UPDATE patients SET {assignments} WHERE id = ?",
                [data[f] for f in FIELDS] + [patient_id],
            )
    except sqlite3.IntegrityError:
        raise DuplicateEmail(data["email"])


def delete_patient(patient_id):
    with connect() as conn:
        conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
