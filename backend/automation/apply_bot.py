"""Apply orchestrator — picks jobs, prepares materials, dispatches to adapters."""

import asyncio
import os
import random
import logging
from datetime import datetime, timezone

from database import get_connection
from automation.adapters.base import ATSAdapter, ApplyResult
from automation.adapters.greenhouse import GreenhouseAdapter
from automation.adapters.lever import LeverAdapter
from automation.adapters.workday import WorkdayAdapter
from services.email_manager import generate_email, send_confirmation_email, capture_confirmation_email

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
RESUME_DIR = os.path.join(DATA_DIR, "resumes")
COVER_LETTER_DIR = os.path.join(DATA_DIR, "cover_letters")

ADAPTERS: dict[str, ATSAdapter] = {
    "greenhouse": GreenhouseAdapter(),
    "lever": LeverAdapter(),
    "workday": WorkdayAdapter(),
}

# Daily application limits
MAX_DAILY_APPLIES = int(os.getenv("MAX_DAILY_APPLIES", "50"))
BATCH_SIZE = int(os.getenv("APPLY_BATCH_SIZE", "10"))
MIN_DELAY_SECONDS = int(os.getenv("APPLY_MIN_DELAY", "30"))
MAX_DELAY_SECONDS = int(os.getenv("APPLY_MAX_DELAY", "90"))


def _get_profile() -> dict:
    """Load profile from DB."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {}
    d = dict(row)
    # Split full_name into first/last for forms that need them
    parts = (d.get("full_name") or "").split(" ", 1)
    d["first_name"] = parts[0] if parts else ""
    d["last_name"] = parts[1] if len(parts) > 1 else ""
    return d


def _get_answer_bank() -> dict:
    """Load answer bank as {question_pattern: answer}."""
    conn = get_connection()
    rows = conn.execute("SELECT question_pattern, answer FROM answer_bank").fetchall()
    conn.close()
    return {r["question_pattern"]: r["answer"] for r in rows}


def _get_resume_path() -> str:
    """Get the most recent resume file."""
    if not os.path.exists(RESUME_DIR):
        return ""
    files = [f for f in os.listdir(RESUME_DIR) if f.lower().endswith((".pdf", ".docx"))]
    if not files:
        return ""
    # Return most recently modified
    files.sort(key=lambda f: os.path.getmtime(os.path.join(RESUME_DIR, f)), reverse=True)
    return os.path.join(RESUME_DIR, files[0])


def _get_cover_letter_path(job_id: int) -> str | None:
    """Check if a cover letter exists for this job."""
    if not os.path.exists(COVER_LETTER_DIR):
        return None
    for f in os.listdir(COVER_LETTER_DIR):
        if f.startswith(f"job_{job_id}_") and f.endswith(".pdf"):
            return os.path.join(COVER_LETTER_DIR, f)
    return None


def _get_pending_jobs(limit: int = BATCH_SIZE) -> list[dict]:
    """Get jobs ready for auto-apply."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, company, title, source_url, source
           FROM jobs
           WHERE status = 'AUTO_APPLY'
           ORDER BY score DESC, date_found ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _count_today_applied() -> int:
    """Count how many jobs were applied to today."""
    conn = get_connection()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM jobs WHERE date_applied LIKE ?",
        (f"{today}%",),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def _update_job_status(
    job_id: int,
    status: str,
    email_used: str = "",
    failure_step: str = "",
):
    """Update job status after apply attempt."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()

    updates = ["status = ?"]
    params = [status]

    if status == "SUBMITTED":
        updates.append("date_applied = ?")
        params.append(now)
    if email_used:
        updates.append("email_used = ?")
        params.append(email_used)
    if failure_step:
        updates.append("failure_step = ?")
        params.append(failure_step)

    params.append(job_id)
    conn.execute(
        f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()
    conn.close()


async def apply_to_job(job: dict, profile: dict, resume_path: str, answers: dict) -> ApplyResult:
    """Apply to a single job using the appropriate adapter."""
    source_url = job.get("source_url", "")
    source = job.get("source", "").lower()

    # Detect platform
    platform = ATSAdapter.detect_platform(source_url)
    if platform == "unknown":
        # Fall back to source field
        platform = source if source in ADAPTERS else "unknown"

    adapter = ADAPTERS.get(platform)
    if not adapter:
        return ApplyResult(
            success=False,
            failure_step="unsupported_platform",
            error_message=f"No adapter for platform: {platform}",
        )

    # Generate a unique email for this application
    email_addr = generate_email(job.get("company", "unknown"))
    if email_addr:
        profile = {**profile, "email": email_addr}

    # Get cover letter if exists
    cover_letter = _get_cover_letter_path(job["id"])

    logger.info(f"Applying to {job['company']} - {job['title']} via {platform}")

    result = await adapter.apply(
        job_url=source_url,
        job_id=job["id"],
        profile=profile,
        resume_path=resume_path,
        cover_letter_path=cover_letter,
        answers=answers,
        company=job.get("company", "unknown"),
        location=job.get("location", ""),
        job_title=job.get("title", ""),
    )

    # Update job status
    if result.success:
        if result.failure_step == "dry_run":
            status = "DRY_RUN_DONE"
        else:
            status = "SUBMITTED"
            # Send our own confirmation email to user
            send_confirmation_email(
                company=job.get("company", ""),
                title=job.get("title", ""),
                email_used=email_addr,
                source_url=source_url,
            )
            # Capture the company's confirmation email (5 min max)
            # Skip security code / verification emails, wait for the real one
            confirmation = await asyncio.to_thread(
                capture_confirmation_email, email_addr, 300,
                skip_subjects=["security code", "verification code"],
            )
            if confirmation:
                result.confirmation_email = confirmation
                logger.info(
                    f"Captured company confirmation: "
                    f"{confirmation.get('subject', '')[:60]}"
                )
            else:
                logger.info(f"No confirmation email within 5 min for {email_addr}, moving on")
        _update_job_status(
            job["id"],
            status,
            email_used=email_addr,
        )
    else:
        # Mark dead/expired pages as SKIPPED so they aren't retried
        if result.failure_step == "page_dead":
            status = "SKIPPED"
            logger.info(f"Job page dead, marking SKIPPED: {source_url}")
        else:
            status = "APPLY_FAILED"
        _update_job_status(
            job["id"],
            status,
            failure_step=result.failure_step or "",
        )

    return result


async def run_apply_batch() -> dict:
    """Run a batch of applications.

    Returns summary: {attempted, submitted, failed, skipped}
    """
    # MAX_DAILY_APPLIES=0 means unlimited
    if MAX_DAILY_APPLIES > 0:
        already_applied = _count_today_applied()
        remaining = MAX_DAILY_APPLIES - already_applied
        if remaining <= 0:
            logger.info(f"Daily limit reached ({MAX_DAILY_APPLIES})")
            return {"attempted": 0, "submitted": 0, "failed": 0, "skipped": 0, "daily_limit": True}
        batch_limit = min(BATCH_SIZE, remaining)
    else:
        batch_limit = BATCH_SIZE

    jobs = _get_pending_jobs(batch_limit)

    if not jobs:
        logger.info("No jobs pending for auto-apply")
        return {"attempted": 0, "submitted": 0, "failed": 0, "skipped": len(jobs)}

    profile = _get_profile()
    if not profile:
        logger.error("No profile configured — cannot apply")
        return {"attempted": 0, "submitted": 0, "failed": 0, "skipped": len(jobs), "error": "no_profile"}

    resume_path = _get_resume_path()
    if not resume_path:
        logger.error("No resume found — cannot apply")
        return {"attempted": 0, "submitted": 0, "failed": 0, "skipped": len(jobs), "error": "no_resume"}

    answers = _get_answer_bank()

    summary = {"attempted": 0, "submitted": 0, "failed": 0, "skipped": 0}

    for job in jobs:
        source_url = job.get("source_url", "")
        platform = ATSAdapter.detect_platform(source_url)

        if platform == "unknown" and job.get("source", "").lower() not in ADAPTERS:
            logger.info(f"Skipping job {job['id']} — unsupported platform")
            summary["skipped"] += 1
            continue

        summary["attempted"] += 1

        result = await apply_to_job(job, profile, resume_path, answers)

        if result.success:
            summary["submitted"] += 1
        else:
            summary["failed"] += 1

        # Stagger: random delay between applications
        if job != jobs[-1]:
            delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            logger.info(f"Waiting {delay}s before next application...")
            await asyncio.sleep(delay)

    logger.info(
        f"Apply batch done: {summary['attempted']} attempted, "
        f"{summary['submitted']} submitted, {summary['failed']} failed"
    )
    return summary


async def run_full_queue() -> dict:
    """Keep running batches until all AUTO_APPLY jobs are processed or daily limit hit."""
    totals = {"attempted": 0, "submitted": 0, "failed": 0, "skipped": 0, "batches": 0}

    while True:
        result = await run_apply_batch()
        totals["batches"] += 1
        totals["attempted"] += result.get("attempted", 0)
        totals["submitted"] += result.get("submitted", 0)
        totals["failed"] += result.get("failed", 0)
        totals["skipped"] += result.get("skipped", 0)

        # Stop if daily limit hit, no jobs left, or an error occurred
        if result.get("daily_limit") or result.get("error"):
            break
        if result.get("attempted", 0) == 0:
            break

    logger.info(
        f"Full queue done: {totals['batches']} batches, "
        f"{totals['attempted']} attempted, {totals['submitted']} submitted, "
        f"{totals['failed']} failed"
    )
    return totals


async def scan_and_apply() -> dict:
    """Full cycle: scan for new jobs, then apply to all matching ones."""
    from scanner.scheduler import run_scan

    logger.info("=== SCAN & APPLY CYCLE START ===")
    scan_result = await run_scan()
    logger.info(f"Scan done: {scan_result}")

    apply_result = await run_full_queue()
    logger.info(f"Apply done: {apply_result}")

    return {
        "scan": scan_result,
        "apply": apply_result,
    }
