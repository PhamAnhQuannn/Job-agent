import asyncio
import logging
import sqlite3
from datetime import datetime, timezone

from scanner.greenhouse import fetch_greenhouse_boards
from scanner.lever import fetch_lever_boards
from services.filter_engine import filter_job, compute_dedup_hash
from database import get_connection

logger = logging.getLogger(__name__)

# --- Board Configuration ---
# Add company board tokens here to scan them.

GREENHOUSE_BOARDS = [
    # --- Working boards (verified) ---
    "mongodb",
    "figma",
    "stripe",
    "airbnb",
    "airtable",
    "cloudflare",
    "twilio",
    "elastic",
    "hubspot",
    "squarespace",
    "pinterest",
    "cockroachlabs",
    "databricks",
    "gitlab",
    "gusto",
    "affirm",
    "brex",
    "reddit",
    "discord",
    "verkada",
    "watershed",
    "duolingo",
    # --- Fixed slugs ---
    "doordashusa",        # was "doordash"
    "andurilindustries",  # was "anduril"
    "tripactions",        # was "navan"
    # --- Newly added ---
    "datadog",
    "okta",
    "zscaler",
    "roblox",
    "toast",
    "sofi",
    "janestreet",
    "celonis",
    "clickhouse",
    "fivetran",
    "lyft",
    "robinhood",
    "asana",
    "coinbase",
    "imc",
    "flexport",
    "instacart",
    "contentful",
    "dropbox",
    "block",
    "postman",
    "abnormalsecurity",
    "chime",
    "vercel",
    "epicgames",
    "opendoor",
    "waymo",
    "coupang",
    "scopely",
    "samsara",
    "mixpanel",
    "launchdarkly",
    "applovin",
    "amplitude",
    "marqeta",
    "starburst",
    "movableink",
    "axiom",
    "motive",
]

LEVER_BOARDS = [
    "netflix",
    "anyscale",
    # --- Fixed: moved from broken to correct platform ---
    "plaid",          # Plaid uses Lever, not Greenhouse
    # --- Newly added ---
    "palantir",
    "shieldai",
    "mistral",
    "outreach",
    "secureframe",
    "neon",
    "wealthfront",
    "clari",
]


async def fetch_all_jobs() -> list[dict]:
    """Fetch jobs from all configured sources."""
    all_jobs = []

    if GREENHOUSE_BOARDS:
        gh_jobs = await fetch_greenhouse_boards(GREENHOUSE_BOARDS)
        all_jobs.extend(gh_jobs)
        logger.info(f"Greenhouse total: {len(gh_jobs)} jobs")

    if LEVER_BOARDS:
        lv_jobs = await fetch_lever_boards(LEVER_BOARDS)
        all_jobs.extend(lv_jobs)
        logger.info(f"Lever total: {len(lv_jobs)} jobs")

    return all_jobs


def process_and_store_jobs(raw_jobs: list[dict]) -> dict:
    """Filter, dedup, and store jobs in the database.

    Returns summary: {new, duplicates, matched, review, skipped}
    """
    conn = get_connection()
    summary = {"new": 0, "duplicates": 0, "matched": 0, "review": 0, "skipped": 0}

    for rj in raw_jobs:
        company = rj["company"]
        title = rj["title"]
        location = rj.get("location")
        description = rj.get("description")
        source = rj.get("source", "unknown")
        source_url = rj.get("source_url")

        # Compute dedup hash
        dedup_hash = compute_dedup_hash(company, title, location)

        # Check for duplicate
        existing = conn.execute(
            "SELECT id FROM jobs WHERE dedup_hash = ?", (dedup_hash,)
        ).fetchone()

        if existing:
            summary["duplicates"] += 1
            continue

        # Also check by source_url if present
        if source_url:
            url_exists = conn.execute(
                "SELECT id FROM jobs WHERE source_url = ?", (source_url,)
            ).fetchone()
            if url_exists:
                summary["duplicates"] += 1
                continue

        # Run filter engine
        result = filter_job(company, title, location, description)

        try:
            conn.execute(
                """INSERT INTO jobs
                   (company, title, location, description, source, source_url,
                    dedup_hash, score, status, date_found)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company, title, location, description, source, source_url,
                    result["dedup_hash"], result["score"], result["status"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            summary["new"] += 1

            if result["status"] == "AUTO_APPLY":
                summary["matched"] += 1
            elif result["status"] == "REVIEW_NEEDED":
                summary["review"] += 1
            elif result["status"] == "SKIPPED":
                summary["skipped"] += 1

        except sqlite3.IntegrityError:
            # Race condition or constraint violation — treat as duplicate
            summary["duplicates"] += 1

    conn.commit()
    conn.close()

    logger.info(
        f"Scan complete: {summary['new']} new, {summary['duplicates']} dupes, "
        f"{summary['matched']} matched, {summary['review']} review, {summary['skipped']} skipped"
    )
    return summary


async def run_scan() -> dict:
    """Full scan cycle: fetch → filter → store."""
    logger.info("Starting scan cycle...")
    raw_jobs = await fetch_all_jobs()
    logger.info(f"Fetched {len(raw_jobs)} total raw jobs")

    if not raw_jobs:
        logger.info("No jobs fetched, skipping processing")
        return {"new": 0, "duplicates": 0, "matched": 0, "review": 0, "skipped": 0}

    summary = process_and_store_jobs(raw_jobs)
    return summary
