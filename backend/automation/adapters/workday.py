"""Workday ATS adapter — stub for future implementation.

Workday forms are complex and vary significantly between employers.
This is a placeholder that will be filled in incrementally.
"""

import logging
from automation.adapters.base import ATSAdapter, ApplyResult

logger = logging.getLogger(__name__)


class WorkdayAdapter(ATSAdapter):
    platform_name = "workday"

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
        logger.warning(f"Workday adapter not yet implemented for job {job_id}")
        return ApplyResult(
            success=False,
            failure_step="unsupported_platform",
            error_message="Workday adapter not yet implemented",
        )
