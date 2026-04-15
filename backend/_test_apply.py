"""Test a single job apply in headed mode so you can watch the form being filled."""
import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
os.environ["DRY_RUN"] = "true"
os.environ["HEADLESS"] = "false"

from automation.apply_bot import apply_to_job

async def main():
    from automation.apply_bot import _get_profile, _get_answer_bank, _get_resume_path
    from database import get_connection

    profile = _get_profile()
    answers = _get_answer_bank()
    resume_path = _get_resume_path()

    conn = get_connection()
    row = conn.execute("SELECT id, company, title, source_url, source, location FROM jobs WHERE id = 70862").fetchone()
    conn.close()

    job = dict(row)
    print(f"Applying to: {job['company']} - {job['title']}")
    print(f"URL: {job['source_url']}")
    print(f"Resume: {resume_path}")
    print(f"Answers loaded: {len(answers)}")
    print()

    result = await apply_to_job(job, profile, resume_path, answers)
    print()
    print("=== RESULT ===")
    print(f"  success: {result.success}")
    print(f"  failure_step: {result.failure_step}")
    print(f"  error_message: {result.error_message}")
    print(f"  confirmation_email: {result.confirmation_email}")

asyncio.run(main())
