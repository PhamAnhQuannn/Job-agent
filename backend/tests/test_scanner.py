import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scanner.scheduler import process_and_store_jobs
from services.filter_engine import compute_dedup_hash
from database import get_connection, init_db


def setup():
    """Reset test DB state."""
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()


def test_process_stores_jobs():
    """Jobs get inserted with correct status and dedup hash."""
    setup()
    raw = [
        {
            "company": "TestCo",
            "title": "Software Engineer Intern",
            "location": "San Francisco, CA",
            "description": "Java, Python, SQL, backend, REST API, Docker",
            "source": "greenhouse",
            "source_url": "https://example.com/job/1",
        },
        {
            "company": "SkipCo",
            "title": "Mechanical Engineer",
            "location": "Detroit, MI",
            "description": "CAD, SolidWorks, AutoCAD",
            "source": "greenhouse",
            "source_url": "https://example.com/job/2",
        },
    ]
    summary = process_and_store_jobs(raw)
    assert summary["new"] == 2
    assert summary["matched"] >= 1
    assert summary["skipped"] >= 1

    conn = get_connection()
    rows = conn.execute("SELECT * FROM jobs ORDER BY id").fetchall()
    conn.close()

    assert len(rows) == 2
    # First job should be AUTO_APPLY (SWE intern + strong skills + US)
    assert dict(rows[0])["status"] == "AUTO_APPLY"
    # Second should be SKIPPED (not intern title)
    assert dict(rows[1])["status"] == "SKIPPED"


def test_dedup_blocks_duplicates():
    """Same job inserted twice → second is a duplicate."""
    setup()
    raw = [
        {
            "company": "DupeCo",
            "title": "Backend Developer",
            "location": "NYC",
            "description": "Java, Spring Boot, SQL",
            "source": "lever",
            "source_url": "https://example.com/job/dup1",
        },
    ]
    summary1 = process_and_store_jobs(raw)
    assert summary1["new"] == 1

    # Insert same job again
    summary2 = process_and_store_jobs(raw)
    assert summary2["duplicates"] == 1
    assert summary2["new"] == 0

    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    assert count == 1  # Still only 1 row


def test_url_dedup():
    """Same source_url but different title → still deduped by URL."""
    setup()
    raw1 = [
        {
            "company": "Co1",
            "title": "SWE Intern",
            "location": "CA",
            "description": "Python",
            "source": "greenhouse",
            "source_url": "https://example.com/same-url",
        },
    ]
    raw2 = [
        {
            "company": "Co1",
            "title": "SWE Intern - Updated Title",
            "location": "CA",
            "description": "Python",
            "source": "greenhouse",
            "source_url": "https://example.com/same-url",
        },
    ]
    process_and_store_jobs(raw1)
    summary = process_and_store_jobs(raw2)
    assert summary["duplicates"] == 1

    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    assert count == 1


def test_hard_skip_citizenship():
    """Job requiring US citizenship → SKIPPED."""
    setup()
    raw = [
        {
            "company": "GovCo",
            "title": "Software Engineer Intern",
            "location": "DC",
            "description": "Java, Python. U.S. citizen required. Security clearance.",
            "source": "greenhouse",
            "source_url": "https://example.com/gov1",
        },
    ]
    summary = process_and_store_jobs(raw)
    assert summary["skipped"] == 1

    conn = get_connection()
    row = conn.execute("SELECT status FROM jobs WHERE company = 'GovCo'").fetchone()
    conn.close()
    assert row[0] == "SKIPPED"


def test_return_to_school_skip():
    """Job requiring return to school → SKIPPED."""
    setup()
    raw = [
        {
            "company": "BigTech",
            "title": "Software Engineer Intern",
            "location": "CA",
            "description": "Python, Java. Must return to school after the internship.",
            "source": "lever",
            "source_url": "https://example.com/rts1",
        },
    ]
    summary = process_and_store_jobs(raw)
    assert summary["skipped"] == 1


def test_no_jobs_returns_empty_summary():
    """Empty input → all zeros."""
    setup()
    summary = process_and_store_jobs([])
    assert summary["new"] == 0
    assert summary["duplicates"] == 0


def test_unicode_job():
    """Job with unicode characters saves correctly."""
    setup()
    raw = [
        {
            "company": "Ünïcödé Corp",
            "title": "Software Engineer Intern — Bäckend",
            "location": "San Francisco, CA",
            "description": "Python, Java, SQL, à la carte résumé handling",
            "source": "lever",
            "source_url": "https://example.com/unicode1",
        },
    ]
    summary = process_and_store_jobs(raw)
    assert summary["new"] == 1

    conn = get_connection()
    row = conn.execute("SELECT company, title FROM jobs").fetchone()
    conn.close()
    assert "Ünïcödé" in row[0]


def test_no_description_review():
    """Job with no description → stored, goes to REVIEW."""
    setup()
    raw = [
        {
            "company": "MinimalCo",
            "title": "Software Engineer Intern",
            "location": "Remote",
            "description": "",
            "source": "greenhouse",
            "source_url": "https://example.com/nodesc1",
        },
    ]
    summary = process_and_store_jobs(raw)
    assert summary["new"] == 1

    conn = get_connection()
    row = conn.execute("SELECT status FROM jobs WHERE company = 'MinimalCo'").fetchone()
    conn.close()
    # Title-only match → REVIEW_NEEDED
    assert row[0] == "REVIEW_NEEDED"
