from fastapi import APIRouter
import asyncio
from automation.apply_bot import run_apply_batch, run_full_queue, scan_and_apply, apply_to_job, _get_profile, _get_resume_path, _get_answer_bank
from automation.adapters.base import ATSAdapter
from database import get_connection

router = APIRouter(prefix="/api/apply", tags=["apply"])


@router.post("/batch")
async def trigger_batch():
    """Run a single batch of auto-applications (up to BATCH_SIZE)."""
    summary = await run_apply_batch()
    return summary


@router.post("/drain")
async def trigger_drain():
    """Apply to ALL pending AUTO_APPLY jobs (loops batches until queue empty or daily limit)."""
    summary = await run_full_queue()
    return summary


@router.post("/cycle")
async def trigger_cycle():
    """Full cycle: scan for new jobs, then apply to all matching ones."""
    result = await scan_and_apply()
    return result


@router.post("/single/{job_id}")
async def apply_single(job_id: int):
    """Apply to a specific job by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, company, title, source_url, source FROM jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    conn.close()

    if not row:
        return {"error": "Job not found"}

    job = dict(row)
    profile = _get_profile()
    resume_path = _get_resume_path()
    answers = _get_answer_bank()

    if not profile:
        return {"error": "No profile configured"}
    if not resume_path:
        return {"error": "No resume uploaded"}

    result = await apply_to_job(job, profile, resume_path, answers)

    return {
        "success": result.success,
        "confirmation_email": result.confirmation_email.get("subject") if result.confirmation_email else None,
        "failure_step": result.failure_step,
        "error": result.error_message,
    }


@router.get("/detect-platform")
def detect_platform(url: str):
    """Detect which ATS platform a URL belongs to."""
    return {"platform": ATSAdapter.detect_platform(url)}
