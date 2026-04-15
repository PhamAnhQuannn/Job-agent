import httpx
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

# Lever exposes jobs at https://api.lever.co/v0/postings/{company}
# Each posting has title, categories, description, lists, and additional fields.

LEVER_API = "https://api.lever.co/v0/postings/{company}"


async def fetch_lever_board(company: str) -> list[dict]:
    """Fetch all jobs from a Lever company board.

    Args:
        company: The company identifier (e.g. 'netflix', 'twitch')

    Returns:
        List of normalized job dicts.
    """
    url = LEVER_API.format(company=company)
    jobs = []

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning(f"Lever board '{company}' returned {resp.status_code}")
            return []

        postings = resp.json()
        if not isinstance(postings, list):
            logger.warning(f"Lever '{company}': unexpected response format")
            return []

        logger.info(f"Lever '{company}': found {len(postings)} listings")

        for post in postings:
            title = post.get("text", "")
            location = post.get("categories", {}).get("location", "")
            description_html = post.get("descriptionPlain") or post.get("description", "")

            # If HTML, extract text
            if "<" in description_html:
                soup = BeautifulSoup(description_html, "html.parser")
                description = soup.get_text(separator="\n", strip=True)
            else:
                description = description_html

            # Append additional/lists sections
            for section in post.get("lists", []):
                section_text = section.get("text", "")
                section_content = section.get("content", "")
                if section_content and "<" in section_content:
                    soup = BeautifulSoup(section_content, "html.parser")
                    section_content = soup.get_text(separator="\n", strip=True)
                if section_text or section_content:
                    description += f"\n\n{section_text}\n{section_content}"

            apply_url = post.get("hostedUrl", "") or post.get("applyUrl", "")

            jobs.append({
                "company": company,
                "title": title,
                "location": location,
                "description": description.strip(),
                "source": "lever",
                "source_url": apply_url,
            })

    return jobs


async def fetch_lever_boards(companies: list[str]) -> list[dict]:
    """Fetch jobs from multiple Lever boards."""
    all_jobs = []
    for company in companies:
        try:
            jobs = await fetch_lever_board(company)
            all_jobs.extend(jobs)
        except Exception as e:
            logger.error(f"Error scraping Lever '{company}': {e}")
    return all_jobs
