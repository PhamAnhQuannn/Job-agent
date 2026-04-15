from fastapi import APIRouter, Depends, UploadFile, File
import sqlite3
import os
import shutil
from database import get_db

router = APIRouter(prefix="/api/resume", tags=["resume"])

RESUME_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "resumes")


@router.post("")
async def upload_resume(file: UploadFile = File(...)):
    os.makedirs(RESUME_DIR, exist_ok=True)
    file_path = os.path.join(RESUME_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": file.filename, "path": file_path}


@router.get("")
def list_resumes():
    os.makedirs(RESUME_DIR, exist_ok=True)
    files = os.listdir(RESUME_DIR)
    return {"resumes": files}
