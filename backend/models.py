from pydantic import BaseModel
from typing import Optional


class ProfileBase(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    school: Optional[str] = None
    degree: Optional[str] = None
    graduation_date: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    location: Optional[str] = None
    work_authorization: Optional[str] = None
    needs_sponsorship: bool = False
    willing_to_relocate: bool = True
    target_roles: Optional[str] = None
    preferred_locations: Optional[str] = None


class ProfileResponse(ProfileBase):
    id: int


class JobBase(BaseModel):
    company: str
    title: str
    location: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None


class JobResponse(JobBase):
    id: int
    dedup_hash: Optional[str] = None
    score: int = 0
    status: str = "FOUND"
    date_found: Optional[str] = None
    date_applied: Optional[str] = None
    email_used: Optional[str] = None
    cover_letter_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    failure_step: Optional[str] = None
    notes: Optional[str] = None


class JobStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class AnswerBase(BaseModel):
    question_pattern: str
    answer: str
    category: Optional[str] = None


class AnswerResponse(AnswerBase):
    id: int


class AssessmentResponse(BaseModel):
    id: int
    job_id: int
    platform: Optional[str] = None
    oa_link: Optional[str] = None
    deadline: Optional[str] = None
    status: str = "PENDING"
    received_date: Optional[str] = None
    notes: Optional[str] = None


class DailyStatsResponse(BaseModel):
    date: str
    jobs_found: int = 0
    auto_applied: int = 0
    review_queued: int = 0
    skipped: int = 0
    duplicates: int = 0
    failed: int = 0
    responses: int = 0
