import httpx
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

# Greenhouse exposes jobs as JSON at /boards/{board}/jobs
# and individual listings at /boards/{board}/jobs/{id}

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
GREENHOUSE_JOB = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"


async def fetch_greenhouse_board(board_token: str) -> list[dict]:
    """Fetch all jobs from a Greenhouse board.

    Args:
        board_token: The board identifier (e.g. 'google', 'airbnb')

    Returns:
        List of normalized job dicts with keys:
        company, title, location, description, source, source_url
    """
    url = GREENHOUSE_API.format(board=board_token)
    jobs = []

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params={"content": "true"})
        if resp.status_code != 200:
            logger.warning(f"Greenhouse board '{board_token}' returned {resp.status_code}")
            return []

        data = resp.json()
        raw_jobs = data.get("jobs", [])
        logger.info(f"Greenhouse '{board_token}': found {len(raw_jobs)} listings")

        for rj in raw_jobs:
            title = rj.get("title", "")
            location = ""
            if rj.get("location"):
                location = rj["location"].get("name", "")

            # Description is HTML — extract text
            content_html = rj.get("content", "")
            description = ""
            if content_html:
                soup = BeautifulSoup(content_html, "html.parser")
                description = soup.get_text(separator="\n", strip=True)

            job_url = rj.get("absolute_url", "")

            jobs.append({
                "company": board_token,
                "title": title,
                "location": location,
                "description": description,
                "source": "greenhouse",
                "source_url": job_url,
            })

    return jobs


async def fetch_greenhouse_boards(board_tokens: list[str]) -> list[dict]:
    """Fetch jobs from multiple Greenhouse boards."""
    all_jobs = []
    for token in board_tokens:
        try:
            jobs = await fetch_greenhouse_board(token)
            all_jobs.extend(jobs)
        except Exception as e:
            logger.error(f"Error scraping Greenhouse '{token}': {e}")
    return all_jobs
