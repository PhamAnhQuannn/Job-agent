"""Base class for ATS platform adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ApplyResult:
    """Result of an application attempt."""
    success: bool
    confirmation_email: dict | None = None
    failure_step: str | None = None
    error_message: str | None = None


class ATSAdapter(ABC):
    """Interface for ATS-specific form fillers."""

    platform_name: str = "unknown"

    @abstractmethod
    async def apply(
        self,
        job_url: str,
        job_id: int,
        profile: dict,
        resume_path: str,
        cover_letter_path: str | None = None,
        answers: dict | None = None,
        company: str = "",
        location: str = "",
        job_title: str = "",
    ) -> ApplyResult:
        """Fill and submit an application form.

        Args:
            job_url: Direct URL to the job posting or application page
            job_id: Internal job ID for screenshots/tracking
            profile: User profile dict (name, email, phone, etc.)
            resume_path: Absolute path to resume file
            cover_letter_path: Optional path to cover letter PDF
            answers: Dict of question patterns → answers
            company: Company name for screenshot filename
            location: Job location for screenshot filename
            job_title: Job title for AI answer context

        Returns:
            ApplyResult with success/failure status
        """
        ...

    @staticmethod
    def detect_platform(url: str) -> str:
        """Detect which ATS platform a URL belongs to."""
        url_lower = url.lower()
        if "greenhouse.io" in url_lower or "boards.greenhouse" in url_lower:
            return "greenhouse"
        if "lever.co" in url_lower or "jobs.lever" in url_lower:
            return "lever"
        if "myworkdayjobs.com" in url_lower or "workday" in url_lower:
            return "workday"
        if "icims" in url_lower:
            return "icims"
        if "smartrecruiters" in url_lower:
            return "smartrecruiters"
        return "unknown"
