from fastapi import APIRouter, Depends, HTTPException, Query
import sqlite3
from database import get_db
from models import JobBase, JobResponse, JobStatusUpdate

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
def list_jobs(
    status: str = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    db: sqlite3.Connection = Depends(get_db),
):
    if status:
        rows = db.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY date_found DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM jobs ORDER BY date_found DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/stats")
def job_stats(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
    ).fetchall()
    return {row["status"]: row["count"] for row in rows}


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


@router.patch("/{job_id}/status", response_model=JobResponse)
def update_job_status(
    job_id: int,
    update: JobStatusUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    valid_statuses = {
        "FOUND", "DUPLICATE", "MATCHED", "SKIPPED", "DRAFTED",
        "REVIEW_NEEDED", "AUTO_APPLY", "APPLYING", "SUBMITTED",
        "APPLY_FAILED", "DRY_RUN_DONE", "FAILED",
        "REJECTED", "INTERVIEW", "OFFER", "WITHDRAWN",
    }
    if update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    if update.notes:
        db.execute(
            "UPDATE jobs SET status = ?, notes = ? WHERE id = ?",
            (update.status, update.notes, job_id),
        )
    else:
        db.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (update.status, job_id),
        )
    db.commit()

    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)
