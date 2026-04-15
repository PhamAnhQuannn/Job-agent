from fastapi import APIRouter, Depends
import sqlite3
from database import get_db
from services.email_manager import generate_email, process_emails

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("")
def list_emails(
    email_type: str | None = None,
    job_id: int | None = None,
    limit: int = 50,
    db: sqlite3.Connection = Depends(get_db),
):
    """List stored emails with optional filtering."""
    query = "SELECT * FROM emails"
    conditions = []
    params = []

    if email_type:
        conditions.append("email_type = ?")
        params.append(email_type)
    if job_id:
        conditions.append("job_id = ?")
        params.append(job_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY received_date DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/assessments")
def list_assessments(
    status: str | None = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """List OA assessments with optional status filter."""
    query = """
        SELECT a.*, j.company, j.title
        FROM assessments a
        LEFT JOIN jobs j ON a.job_id = j.id
    """
    params = []

    if status:
        query += " WHERE a.status = ?"
        params.append(status)

    query += " ORDER BY a.deadline ASC NULLS LAST"

    rows = db.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@router.post("/fetch")
def fetch_emails():
    """Trigger manual email fetch and processing."""
    summary = process_emails()
    return summary


@router.post("/generate-address")
def generate_address(company: str, role_suffix: str = ""):
    """Generate a unique email address for a job application."""
    address = generate_email(company, role_suffix)
    if not address:
        return {"error": "No email domain or Gmail configured in .env"}
    return {"email": address}


@router.patch("/assessments/{assessment_id}")
def update_assessment(
    assessment_id: int,
    status: str,
    notes: str | None = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """Update an assessment status (PENDING, COMPLETED, EXPIRED)."""
    valid = {"PENDING", "COMPLETED", "EXPIRED"}
    if status not in valid:
        return {"error": f"Invalid status. Must be one of {valid}"}

    if notes:
        db.execute(
            "UPDATE assessments SET status = ?, notes = ? WHERE id = ?",
            (status, notes, assessment_id),
        )
    else:
        db.execute(
            "UPDATE assessments SET status = ? WHERE id = ?",
            (status, assessment_id),
        )
    db.commit()
    return {"updated": assessment_id, "status": status}
