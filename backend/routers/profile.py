from fastapi import APIRouter, Depends
import sqlite3
from database import get_db
from models import ProfileBase, ProfileResponse

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if not row:
        return {"id": 1, "full_name": "", "email": ""}
    return dict(row)


@router.put("", response_model=ProfileResponse)
def update_profile(profile: ProfileBase, db: sqlite3.Connection = Depends(get_db)):
    db.execute("""
        INSERT INTO profile (id, full_name, email, phone, school, degree,
            graduation_date, linkedin, github, portfolio, location,
            work_authorization, needs_sponsorship, willing_to_relocate,
            target_roles, preferred_locations)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            full_name=excluded.full_name, email=excluded.email,
            phone=excluded.phone, school=excluded.school,
            degree=excluded.degree, graduation_date=excluded.graduation_date,
            linkedin=excluded.linkedin, github=excluded.github,
            portfolio=excluded.portfolio, location=excluded.location,
            work_authorization=excluded.work_authorization,
            needs_sponsorship=excluded.needs_sponsorship,
            willing_to_relocate=excluded.willing_to_relocate,
            target_roles=excluded.target_roles,
            preferred_locations=excluded.preferred_locations
    """, (
        profile.full_name, profile.email, profile.phone, profile.school,
        profile.degree, profile.graduation_date, profile.linkedin,
        profile.github, profile.portfolio, profile.location,
        profile.work_authorization, profile.needs_sponsorship,
        profile.willing_to_relocate, profile.target_roles,
        profile.preferred_locations
    ))
    db.commit()
    return {"id": 1, **profile.model_dump()}
