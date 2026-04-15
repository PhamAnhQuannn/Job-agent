from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3
import os
from database import get_db
from services.ai_writer import generate_cover_letter, generate_answer
from services.pdf_export import save_cover_letter_pdf

router = APIRouter(prefix="/api/ai", tags=["ai"])


class CoverLetterRequest(BaseModel):
    company: str
    role_title: str
    job_description: str
    save_pdf: bool = True


class CoverLetterResponse(BaseModel):
    letter: str
    pdf_path: str | None = None
    word_count: int


class AnswerRequest(BaseModel):
    question: str
    company: str | None = None
    role_title: str | None = None


class AnswerResponse(BaseModel):
    answer: str


@router.post("/cover-letter", response_model=CoverLetterResponse)
async def create_cover_letter(req: CoverLetterRequest, db: sqlite3.Connection = Depends(get_db)):
    """Generate a cover letter for a job."""
    letter = await generate_cover_letter(req.company, req.role_title, req.job_description)
    word_count = len(letter.split())

    pdf_path = None
    if req.save_pdf:
        row = db.execute("SELECT full_name FROM profile WHERE id = 1").fetchone()
        name = dict(row)["full_name"] if row else "Applicant"
        pdf_path = save_cover_letter_pdf(letter, req.company, req.role_title, name)

    return CoverLetterResponse(letter=letter, pdf_path=pdf_path, word_count=word_count)


@router.post("/cover-letter/{job_id}", response_model=CoverLetterResponse)
async def create_cover_letter_for_job(job_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Generate cover letter from an existing job in the database."""
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    job = dict(row)
    letter = await generate_cover_letter(job["company"], job["title"], job.get("description") or "")
    word_count = len(letter.split())

    profile_row = db.execute("SELECT full_name FROM profile WHERE id = 1").fetchone()
    name = dict(profile_row)["full_name"] if profile_row else "Applicant"
    pdf_path = save_cover_letter_pdf(letter, job["company"], job["title"], name)

    # Save path to job record
    db.execute("UPDATE jobs SET cover_letter_path = ? WHERE id = ?", (pdf_path, job_id))
    db.commit()

    return CoverLetterResponse(letter=letter, pdf_path=pdf_path, word_count=word_count)


@router.post("/answer", response_model=AnswerResponse)
async def create_answer(req: AnswerRequest):
    """Generate an answer for an application question."""
    answer = await generate_answer(req.question, req.company, req.role_title)
    return AnswerResponse(answer=answer)


@router.get("/cover-letter/{job_id}/pdf")
def download_cover_letter(job_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Download the PDF cover letter for a job."""
    row = db.execute("SELECT cover_letter_path FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row or not dict(row)["cover_letter_path"]:
        raise HTTPException(status_code=404, detail="No cover letter found for this job")

    path = dict(row)["cover_letter_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))
