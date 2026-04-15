import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "job_agent.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY DEFAULT 1,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            school TEXT,
            degree TEXT,
            graduation_date TEXT,
            linkedin TEXT,
            github TEXT,
            portfolio TEXT,
            location TEXT,
            work_authorization TEXT,
            needs_sponsorship BOOLEAN DEFAULT 0,
            willing_to_relocate BOOLEAN DEFAULT 1,
            target_roles TEXT,
            preferred_locations TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            description TEXT,
            source TEXT,
            source_url TEXT UNIQUE,
            dedup_hash TEXT UNIQUE,
            score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'FOUND',
            date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_applied TIMESTAMP,
            email_used TEXT,
            cover_letter_path TEXT,
            screenshot_path TEXT,
            failure_step TEXT,
            notes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            site_url TEXT,
            email_used TEXT NOT NULL,
            password_encrypted TEXT NOT NULL,
            account_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS answer_bank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_pattern TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES jobs(id),
            platform TEXT,
            oa_link TEXT,
            deadline TIMESTAMP,
            status TEXT DEFAULT 'PENDING',
            received_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES jobs(id),
            from_address TEXT,
            to_address TEXT,
            subject TEXT,
            body_preview TEXT,
            email_type TEXT,
            received_date TIMESTAMP,
            action_needed TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            jobs_found INTEGER DEFAULT 0,
            auto_applied INTEGER DEFAULT 0,
            review_queued INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            duplicates INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            responses INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
