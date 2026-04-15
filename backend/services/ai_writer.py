import os
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("LLM_API_KEY"))

MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# --- Profile context loaded once ---
_profile_cache: dict | None = None


def _get_profile() -> dict:
    global _profile_cache
    if _profile_cache:
        return _profile_cache

    from database import get_connection
    conn = get_connection()
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    if row:
        _profile_cache = dict(row)
    else:
        _profile_cache = {}
    return _profile_cache


def clear_profile_cache():
    global _profile_cache
    _profile_cache = None


COVER_LETTER_SYSTEM = """You are a professional cover letter writer for a software engineering internship applicant.

Write a concise, compelling cover letter (150-300 words) personalized to the specific company and role.

Rules:
- Use the applicant's REAL skills and experience only. Never invent experience.
- Mention the company name and role title naturally.
- Highlight relevant technical skills that match the job description.
- Keep a professional but enthusiastic tone appropriate for an intern.
- Do NOT include placeholder text like [Your Name] or {company}.
- Do NOT include the date, address header, or "Dear Hiring Manager" — just the body paragraphs.
- End with a brief closing statement (no signature block).
- Each letter must be unique — do not repeat the same structure word-for-word."""

ANSWER_SYSTEM = """You are helping a software engineering internship applicant answer application questions.

Rules:
- Use only the applicant's real background provided. Never invent experience.
- Keep answers concise (2-5 sentences) unless the question requires more detail.
- Be specific and professional.
- Do NOT use placeholder text."""


async def generate_cover_letter(
    company: str,
    role_title: str,
    job_description: str,
) -> str:
    """Generate a cover letter for a specific job."""
    profile = _get_profile()

    user_prompt = f"""Write a cover letter for this position:

Company: {company}
Role: {role_title}
Job Description:
{job_description[:2000]}

Applicant Background:
- Name: {profile.get('full_name', 'N/A')}
- School: {profile.get('school', 'N/A')}
- Degree: {profile.get('degree', 'N/A')}
- Graduation: {profile.get('graduation_date', 'N/A')}
- Skills: Java (Spring Boot), Python (Django, FastAPI), TypeScript, JavaScript, React, Next.js, Node.js, SQL, Docker, AWS, Redis, Git, CI/CD
- Projects: VOCO Emergency Dispatch Dashboard (Next.js, Node.js, Socket.IO, Mapbox, Redis, Google Gemini), E-Commercia multi-service platform (Java Spring Boot, NestJS, Django, PostgreSQL, MongoDB, Docker, Terraform)
- Experience: IT Support & Programming Tutor — tutored JavaScript, C++, Python; troubleshot hardware/software
- Work Authorization: OPT (no sponsorship needed)"""

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": COVER_LETTER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=600,
    )

    letter = response.choices[0].message.content.strip()
    logger.info(f"Generated cover letter for {company} — {role_title} ({len(letter.split())} words)")
    return letter


async def generate_answer(
    question: str,
    company: str | None = None,
    role_title: str | None = None,
    options: list[str] | None = None,
) -> str:
    """Generate an answer for an application question."""
    profile = _get_profile()

    context = ""
    if company:
        context += f"\nCompany: {company}"
    if role_title:
        context += f"\nRole: {role_title}"

    options_instruction = ""
    if options:
        opts_list = ", ".join(f'"{o}"' for o in options)
        options_instruction = (
            f"\n\nThis is a dropdown question. You MUST pick exactly one of "
            f"these options: [{opts_list}]. Reply with only the chosen option text, "
            f"nothing else."
        )

    user_prompt = f"""Answer this application question:

Question: {question}
{context}

Applicant Background:
- Name: {profile.get('full_name', 'N/A')}
- School: {profile.get('school', 'N/A')}, {profile.get('degree', 'N/A')} (graduating {profile.get('graduation_date', 'N/A')})
- Skills: Java (Spring Boot), Python (Django, FastAPI), TypeScript, JavaScript, React, Next.js, Node.js, SQL, Docker, AWS
- Projects: VOCO (real-time emergency dashboard), E-Commercia (multi-service e-commerce platform)
- Experience: IT Support & Programming Tutor at College of Alameda
- Work Authorization: OPT (no sponsorship needed){options_instruction}"""

    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=300,
    )

    answer = response.choices[0].message.content.strip()
    logger.info(f"Generated answer for question: {question[:50]}...")
    return answer
