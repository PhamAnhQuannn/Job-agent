import re
import hashlib

# --- Keyword Configuration ---

# GATE 1: Title must contain an intern keyword
TITLE_INTERN_REQUIRED = [
    "intern", "internship", "co-op", "coop",
]

# GATE 2: Title must also contain a SWE keyword (bachelor-level software engineering only)
TITLE_SWE_REQUIRED = [
    "software engineer", "software developer", "swe",
    "backend developer", "backend engineer",
    "frontend developer", "frontend engineer",
    "front end developer", "front end engineer",
    "front-end developer", "front-end engineer",
    "full stack developer", "full stack engineer",
    "fullstack developer", "fullstack engineer",
    "full-stack developer", "full-stack engineer",
    "web developer", "web engineer",
    "software development engineer", "software engineering",
]

# Backend-focus bonus keywords in title (+1 extra)
TITLE_BACKEND_BONUS = [
    "backend", "back end", "back-end",
    "server", "api",
]

# US location patterns — job must be in the US
_US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "mississippi", "missouri", "montana", "nebraska",
    "nevada", "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "district of columbia",
]

_US_STATE_ABBREVS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
]

_US_LOCATION_KEYWORDS = [
    "united states", "usa", "u.s.", "us-", "remote",
]

# Positive skill keywords (matched in description)
SKILL_POSITIVE = [
    "java", "python", "javascript", "typescript",
    "spring boot", "spring", "django", "fastapi",
    "react", "next.js", "nextjs", "node.js", "nodejs",
    "sql", "postgresql", "mongodb", "redis",
    "rest api", "restful", "graphql",
    "docker", "kubernetes", "aws", "cloud",
    "git", "ci/cd", "terraform",
    "html", "css", "tailwind",
    "socket.io", "websocket",
    "c++",
]

# Negative keywords — wrong field / not a fit
NEGATIVE_KEYWORDS = [
    "mechanical engineer", "civil engineer", "chemical engineer",
    "electrical engineer", "biomedical",
    "cad", "solidworks", "autocad", "matlab",
    "robotics", "embedded systems", "firmware",
    "hardware engineer", "fpga", "vhdl", "verilog",
    "pharmaceutical", "clinical", "nursing",
    "marketing manager", "sales representative",
    "accounting", "finance analyst",
]

# Title skip patterns — reject based on title alone (not bachelor SWE)
TITLE_SKIP_KEYWORDS = [
    "phd",
    "ph.d",
    "master",
    "masters",
    "mba",
    "skillbridge",
    "skill bridge",
    "skill-bridge",
    "apprenticeship",
    "staff",
    "principal",
    "lead",
    "manager",
    "director",
]

# Non-US country/region names in title — catch mis-located international roles
TITLE_NON_US_LOCATIONS = [
    "france", "poland", "germany", "uk", "london", "ireland", "canada",
    "india", "japan", "korea", "china", "singapore", "australia",
    "brazil", "mexico", "netherlands", "amsterdam", "sweden", "denmark",
    "spain", "italy", "switzerland", "israel", "dubai", "emea", "apac",
    "latam", "europe", "asia",
]

# Hard-skip phrases — instant rejection
HARD_SKIP_PHRASES = [
    # Citizenship / authorization restrictions
    "u.s. citizen required",
    "us citizen required",
    "u.s. citizenship required",
    "us citizenship required",
    "must be a u.s. citizen",
    "must be a us citizen",
    "united states citizen",
    "security clearance required",
    "top secret clearance",
    "ts/sci",
    "public trust clearance",
    "dod clearance",
    "permanent resident required",
    "no opt",
    "no sponsorship",
    "without sponsorship",
    "citizens only",
    "u.s. persons",
    "green card required",
    # Return-to-school after internship (user graduates May 2026, can't return)
    "must return to school",
    "returning to school",
    "return to school after",
    "must be returning to school",
    "continuing education after",
    "returning to university",
    "returning to college",
    "go back to school",
    "resume studies after",
    "continue studies after",
    "at least one quarter remaining",
    "at least one semester remaining",
    "at least 1 quarter remaining",
    "at least 1 semester remaining",
    # Degree level — skip if requires above Bachelor's
    "master's degree required",
    "masters degree required",
    "master's degree is required",
    "phd required",
    "ph.d. required",
    "ph.d required",
    "doctorate required",
    "graduate degree required",
    "advanced degree required",
]

# Graduation date pattern — skip if they require graduation AFTER May 2026
GRADUATION_CUTOFF_YEAR = 2026
GRADUATION_CUTOFF_MONTH = 5  # May 2026

_GRAD_DATE_PATTERN = re.compile(
    r"(?:expected|anticipated)?\s*graduat(?:ion|ing|e)"
    r"[^.\n]{0,40}?"
    r"(?:(?:december|fall|november|october|september|august|july|june)\s+2026"
    r"|202[7-9]|20[3-9]\d)",
    re.IGNORECASE,
)

# Thresholds (after passing gates, score is from skill keywords only)
AUTO_APPLY_THRESHOLD = 3
REVIEW_THRESHOLD = 1


def _build_word_pattern(keyword: str) -> re.Pattern:
    """Build a word-boundary regex for a keyword."""
    escaped = re.escape(keyword)
    return re.compile(r"(?<![a-zA-Z])" + escaped + r"(?![a-zA-Z])", re.IGNORECASE)


def _is_us_location(location: str | None) -> bool:
    """Check if a job location is in the United States."""
    if not location:
        return True  # No location listed — don't skip, let it through

    loc_lower = location.lower().strip()

    # Check US keywords
    for kw in _US_LOCATION_KEYWORDS:
        if kw in loc_lower:
            return True

    # Check full state names
    for state in _US_STATES:
        if state in loc_lower:
            return True

    # Check state abbreviations (e.g. "San Francisco, CA")
    for abbr in _US_STATE_ABBREVS:
        # Match ", CA" or "; CA" or "CA " at boundaries
        if re.search(r"(?:^|[,;\s])" + re.escape(abbr) + r"(?:$|[,;\s])", location):
            return True

    return False


def compute_dedup_hash(company: str, title: str, location: str | None) -> str:
    """Hash company + title + location for deduplication."""
    raw = f"{(company or '').strip().lower()}|{(title or '').strip().lower()}|{(location or '').strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def score_job(title: str, description: str | None, location: str | None = None) -> dict:
    """Score a job posting and return scoring breakdown.

    Gate order:
      1. Hard-skip phrases / graduation date
      2. Title must contain intern keyword
      3. Title must contain SWE keyword
      4. Location must be in the US
      5. Then score by skill keywords
    """
    text = f"{title or ''} {description or ''}".lower()
    title_lower = (title or "").lower()
    score = 0
    hard_skip = False
    hard_skip_reason = None
    matched_positive = []
    matched_negative = []
    matched_title = []
    matched_level = []

    # --- GATE 0a: Title skip keywords ---
    for kw in TITLE_SKIP_KEYWORDS:
        if _build_word_pattern(kw).search(title_lower):
            hard_skip = True
            hard_skip_reason = f"title contains '{kw}'"
            break

    # --- GATE 0b: Non-US location in title ---
    if not hard_skip:
        for loc in TITLE_NON_US_LOCATIONS:
            if _build_word_pattern(loc).search(title_lower):
                hard_skip = True
                hard_skip_reason = f"title contains non-US location '{loc}'"
                break

    # --- GATE 0c: Hard-skip phrases in full text ---
    if not hard_skip:
        for phrase in HARD_SKIP_PHRASES:
            if phrase in text:
                hard_skip = True
                hard_skip_reason = phrase
                break

    if not hard_skip and _GRAD_DATE_PATTERN.search(text):
        hard_skip = True
        hard_skip_reason = "graduation date required after May 2026"

    if hard_skip:
        return {
            "score": 0, "decision": "SKIP",
            "hard_skip": True, "hard_skip_reason": hard_skip_reason,
            "matched_positive": [], "matched_negative": [],
            "matched_title": [], "matched_level": [],
        }

    # --- GATE 1: Title must contain intern/internship/co-op ---
    has_intern = False
    for kw in TITLE_INTERN_REQUIRED:
        if _build_word_pattern(kw).search(title_lower):
            has_intern = True
            matched_level.append(kw)
            break

    if not has_intern:
        return {
            "score": 0, "decision": "SKIP",
            "hard_skip": True, "hard_skip_reason": "title missing intern/internship/co-op",
            "matched_positive": [], "matched_negative": [],
            "matched_title": [], "matched_level": [],
        }

    # --- GATE 2: Title must contain SWE keyword ---
    has_swe = False
    for kw in TITLE_SWE_REQUIRED:
        if _build_word_pattern(kw).search(title_lower):
            has_swe = True
            matched_title.append(kw)
            break

    if not has_swe:
        return {
            "score": 0, "decision": "SKIP",
            "hard_skip": True, "hard_skip_reason": "title missing software engineer keyword",
            "matched_positive": [], "matched_negative": [],
            "matched_title": matched_title, "matched_level": matched_level,
        }

    # --- GATE 3: Location must be in the US ---
    if not _is_us_location(location):
        return {
            "score": 0, "decision": "SKIP",
            "hard_skip": True, "hard_skip_reason": f"non-US location: {location}",
            "matched_positive": [], "matched_negative": [],
            "matched_title": matched_title, "matched_level": matched_level,
        }

    # --- Passed all gates — now score by skills ---
    score = 2  # Base score for passing all gates

    # Backend bonus in title (+1 each)
    for kw in TITLE_BACKEND_BONUS:
        if _build_word_pattern(kw).search(title_lower):
            score += 1
            matched_title.append(f"backend:{kw}")

    # Skill positive keywords (+1 each)
    for kw in SKILL_POSITIVE:
        if _build_word_pattern(kw).search(text):
            score += 1
            matched_positive.append(kw)

    # Negative keywords (-2 each)
    for kw in NEGATIVE_KEYWORDS:
        if _build_word_pattern(kw).search(text):
            score -= 2
            matched_negative.append(kw)

    # Determine decision
    if score < 0 or len(matched_negative) >= 2:
        decision = "SKIP"
    elif score >= AUTO_APPLY_THRESHOLD:
        decision = "AUTO_APPLY"
    elif score >= REVIEW_THRESHOLD:
        decision = "REVIEW"
    else:
        decision = "SKIP"

    return {
        "score": score,
        "decision": decision,
        "hard_skip": False,
        "hard_skip_reason": None,
        "matched_positive": matched_positive,
        "matched_negative": matched_negative,
        "matched_title": matched_title,
        "matched_level": matched_level,
    }


def filter_job(company: str, title: str, location: str | None, description: str | None) -> dict:
    """Full filter pipeline: dedup hash + scoring.

    Returns:
        {
            "dedup_hash": str,
            "score": int,
            "status": "MATCHED" | "REVIEW_NEEDED" | "SKIPPED",
            "details": { ... scoring breakdown ... },
        }
    """
    dedup_hash = compute_dedup_hash(company, title, location)
    result = score_job(title, description, location)

    status_map = {
        "AUTO_APPLY": "AUTO_APPLY",
        "REVIEW": "REVIEW_NEEDED",
        "SKIP": "SKIPPED",
    }

    return {
        "dedup_hash": dedup_hash,
        "score": result["score"],
        "status": status_map[result["decision"]],
        "details": result,
    }
