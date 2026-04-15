import os
import re
import time
import smtplib
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv
from database import get_connection

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

logger = logging.getLogger(__name__)

EMAIL_DOMAIN = os.getenv("EMAIL_DOMAIN", "")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))


# --- Email Address Generator ---

def generate_email(company: str, role_suffix: str = "") -> str:
    """Generate a unique per-job email using catch-all domain.

    Format: apply-{company}-{suffix}@{domain}
    If no custom domain, falls back to Gmail with + alias.
    """
    safe_company = re.sub(r"[^a-z0-9]", "", company.lower())[:20]
    safe_suffix = re.sub(r"[^a-z0-9]", "", role_suffix.lower())[:10] if role_suffix else ""
    timestamp = datetime.now(timezone.utc).strftime("%m%d")

    if EMAIL_DOMAIN:
        tag = f"{safe_company}-{timestamp}"
        if safe_suffix:
            tag = f"{safe_company}-{safe_suffix}-{timestamp}"
        return f"apply-{tag}@{EMAIL_DOMAIN}"
    elif GMAIL_ADDRESS:
        # Gmail + alias: user+tag@gmail.com
        local, domain = GMAIL_ADDRESS.split("@")
        tag = f"{safe_company}-{timestamp}"
        if safe_suffix:
            tag = f"{safe_company}-{safe_suffix}-{timestamp}"
        return f"{local}+{tag}@{domain}"
    else:
        return ""


# --- Confirmation Email Sender ---

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


def send_confirmation_email(company: str, title: str, email_used: str, source_url: str = "") -> bool:
    """Send a confirmation email to the user's Gmail after a successful application."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.warning("SMTP credentials not configured, skipping confirmation email")
        return False

    subject = f"Application Submitted: {title} at {company}"
    body = (
        f"Your application has been submitted successfully.\n\n"
        f"Company: {company}\n"
        f"Position: {title}\n"
        f"Email Used: {email_used}\n"
        f"Applied At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
    )
    if source_url:
        body += f"Job URL: {source_url}\n"
    body += "\n— Job Agent"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, GMAIL_ADDRESS, msg.as_string())
        logger.info(f"Confirmation email sent for {company} - {title}")
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")
        return False


# --- IMAP Inbox Reader ---

def _decode_header_value(value: str) -> str:
    """Decode an email header value."""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def fetch_new_emails(limit: int = 50) -> list[dict]:
    """Fetch recent unseen emails from IMAP inbox.

    Returns list of dicts with: from, to, subject, body_preview, date
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.warning("IMAP credentials not configured, skipping email fetch")
        return []

    emails_found = []
    mail = None

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        # Search for unseen emails
        status, message_ids = mail.search(None, "UNSEEN")
        if status != "OK" or not message_ids[0]:
            return []

        ids = message_ids[0].split()[-limit:]  # Most recent N

        for mid in ids:
            status, msg_data = mail.fetch(mid, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            from_addr = _decode_header_value(msg.get("From", ""))
            to_addr = _decode_header_value(msg.get("To", ""))
            subject = _decode_header_value(msg.get("Subject", ""))
            date_str = msg.get("Date", "")

            # Extract body preview
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")
                            break
                    elif ct == "text/html" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")

            body_preview = body[:500] if body else ""

            emails_found.append({
                "from_address": from_addr,
                "to_address": to_addr,
                "subject": subject,
                "body_preview": body_preview,
                "date": date_str,
                "full_body": body,
            })

    except Exception as e:
        logger.error(f"IMAP fetch error: {e}")
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass

    return emails_found


# --- Verification Code Extractor ---

_VERIFY_PATTERNS = [
    # 4-8 digit numeric codes
    re.compile(r"(?:verification|confirm|verify|code|pin|otp)[^.]{0,40}?(\b\d{4,8}\b)", re.IGNORECASE),
    re.compile(r"\b(\d{4,8})\b[^.]{0,40}?(?:verification|confirm|verify|code|pin|otp)", re.IGNORECASE),
    # "Your code is: 123456"
    re.compile(r"(?:code\s*(?:is|:)\s*)(\d{4,8})", re.IGNORECASE),
    # 6-8 character alphanumeric codes (Greenhouse-style)
    re.compile(r"(?:verification|security|confirm)\s*code[^.]{0,40}?(\b[A-Za-z0-9]{6,8}\b)", re.IGNORECASE),
    re.compile(r"(?:code\s*(?:is|:)\s*)([A-Za-z0-9]{6,8})\b", re.IGNORECASE),
    re.compile(r"\b([A-Za-z0-9]{8})\b[^.]{0,20}?(?:to\s+(?:verify|confirm))", re.IGNORECASE),
]

_VERIFY_LINK_PATTERN = re.compile(
    r"(https?://[^\s\"<>]+(?:verify|confirm|activate|validate)[^\s\"<>]*)",
    re.IGNORECASE,
)


def extract_verification(body: str) -> dict | None:
    """Extract verification code or link from email body.

    Returns: {"type": "code"|"link", "value": str} or None
    """
    if not body:
        return None

    # Try numeric codes first
    for pattern in _VERIFY_PATTERNS:
        match = pattern.search(body)
        if match:
            return {"type": "code", "value": match.group(1)}

    # Try verification links
    link_match = _VERIFY_LINK_PATTERN.search(body)
    if link_match:
        return {"type": "link", "value": link_match.group(1)}

    return None


# --- Email-to-Job Matching ---

def match_email_to_job(to_address: str) -> int | None:
    """Match an email's to-address to a job by the email_used field.

    Returns job_id or None.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM jobs WHERE email_used = ?", (to_address,)
    ).fetchone()
    conn.close()

    return row[0] if row else None


def match_email_by_tag(to_address: str) -> int | None:
    """Try to match by extracting the company tag from the email address.

    e.g., apply-google-0414@domain → search for jobs at 'google'
    """
    # Extract tag: apply-{company}-{suffix}@domain or user+{company}-{suffix}@domain
    match = re.match(r"(?:apply-|[^+]+\+)([a-z0-9]+)", to_address.lower())
    if not match:
        return None

    company_tag = match.group(1)
    conn = get_connection()
    # Fuzzy match company name
    row = conn.execute(
        "SELECT id FROM jobs WHERE LOWER(company) LIKE ? ORDER BY date_found DESC LIMIT 1",
        (f"%{company_tag}%",),
    ).fetchone()
    conn.close()

    return row[0] if row else None


# --- OA Detection ---

_OA_PATTERNS = [
    re.compile(r"(https?://[^\s\"<>]*hackerrank\.com[^\s\"<>]*)", re.IGNORECASE),
    re.compile(r"(https?://[^\s\"<>]*codesignal\.com[^\s\"<>]*)", re.IGNORECASE),
    re.compile(r"(https?://[^\s\"<>]*codility\.com[^\s\"<>]*)", re.IGNORECASE),
    re.compile(r"(https?://[^\s\"<>]*hirevue\.com[^\s\"<>]*)", re.IGNORECASE),
    re.compile(r"(https?://[^\s\"<>]*karat\.com[^\s\"<>]*)", re.IGNORECASE),
    re.compile(r"(https?://[^\s\"<>]*leetcode\.com[^\s\"<>]*)", re.IGNORECASE),
]

# Deadline patterns
_DEADLINE_PATTERN = re.compile(
    r"(?:complete|finish|submit|due|deadline|expire|before|by)[^.]{0,60}?"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2},?\s*\d{4})",
    re.IGNORECASE,
)


def detect_oa(body: str) -> dict | None:
    """Detect online assessment links and deadlines in email body.

    Returns: {"platform": str, "link": str, "deadline": str|None} or None
    """
    if not body:
        return None

    for pattern in _OA_PATTERNS:
        match = pattern.search(body)
        if match:
            link = match.group(1)
            platform = "unknown"
            for name in ["hackerrank", "codesignal", "codility", "hirevue", "karat", "leetcode"]:
                if name in link.lower():
                    platform = name
                    break

            deadline = None
            dl_match = _DEADLINE_PATTERN.search(body)
            if dl_match:
                deadline = dl_match.group(1)

            return {"platform": platform, "link": link, "deadline": deadline}

    return None


# --- Process Emails Pipeline ---

def process_emails() -> dict:
    """Fetch new emails, match to jobs, detect OA, extract verification codes.

    Returns summary: {total, matched, oa_found, verifications}
    """
    emails = fetch_new_emails()
    summary = {"total": len(emails), "matched": 0, "oa_found": 0, "verifications": 0}

    conn = get_connection()

    for em in emails:
        to_addr = em["to_address"]
        subject = em["subject"]
        body = em.get("full_body", em.get("body_preview", ""))

        # Match to job
        job_id = match_email_to_job(to_addr)
        if not job_id:
            job_id = match_email_by_tag(to_addr)

        if job_id:
            summary["matched"] += 1

        # Detect email type
        email_type = "general"
        action_needed = None

        # Check for OA
        oa = detect_oa(body)
        if oa:
            email_type = "assessment"
            action_needed = f"OA on {oa['platform']}"
            summary["oa_found"] += 1

            if job_id:
                conn.execute(
                    """INSERT INTO assessments (job_id, platform, oa_link, deadline, status)
                       VALUES (?, ?, ?, ?, 'PENDING')""",
                    (job_id, oa["platform"], oa["link"], oa.get("deadline")),
                )

        # Check for verification
        verification = extract_verification(body)
        if verification:
            email_type = "verification"
            action_needed = f"{verification['type']}: {verification['value']}"
            summary["verifications"] += 1

        # Check for rejection keywords
        if any(kw in (subject + " " + body).lower() for kw in
               ["unfortunately", "not moving forward", "other candidates",
                "we regret", "position has been filled", "not selected"]):
            email_type = "rejection"
            if job_id:
                conn.execute(
                    "UPDATE jobs SET status = 'REJECTED' WHERE id = ? AND status = 'SUBMITTED'",
                    (job_id,),
                )

        # Store email record
        conn.execute(
            """INSERT INTO emails (job_id, from_address, to_address, subject,
               body_preview, email_type, received_date, action_needed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id, em["from_address"], to_addr, subject,
                em.get("body_preview", "")[:500], email_type,
                em.get("date"), action_needed,
            ),
        )

    conn.commit()
    conn.close()

    logger.info(
        f"Processed {summary['total']} emails: {summary['matched']} matched, "
        f"{summary['oa_found']} OA, {summary['verifications']} verifications"
    )
    return summary


# --- Confirmation Email Capture ---

def _extract_email_result(msg, application_email: str) -> dict:
    """Extract email fields into a result dict."""
    from_addr = _decode_header_value(msg.get("From", ""))
    subject = _decode_header_value(msg.get("Subject", ""))
    date_str = msg.get("Date", "")

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
                    break
            elif ct == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="replace")

    return {
        "from_address": from_addr,
        "to_address": application_email,
        "subject": subject,
        "body_preview": body[:500],
        "full_body": body,
        "date": date_str,
    }


def _check_unseen(mail, app_email_lower: str, skip_subjects: list[str],
                  application_email: str) -> dict | None:
    """Check current UNSEEN emails. Returns result dict or None."""
    status, message_ids = mail.search(None, "UNSEEN")
    if status != "OK" or not message_ids[0]:
        return None

    ids = message_ids[0].split()[-20:]
    for mid in ids:
        status, msg_data = mail.fetch(mid, "(RFC822)")
        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        to_addr = _decode_header_value(msg.get("To", "")).lower()
        if app_email_lower not in to_addr:
            continue

        subject = _decode_header_value(msg.get("Subject", ""))
        subj_lower = subject.lower()
        if any(s in subj_lower for s in skip_subjects):
            logger.info(f"Skipping email '{subject[:60]}' (matches skip_subjects), waiting for next…")
            continue

        return _extract_email_result(msg, application_email)

    return None


def _idle_wait(mail, timeout: float) -> bool:
    """Send IMAP IDLE and block until the server signals new mail or timeout.

    Returns True if new mail may have arrived, False on timeout.
    """
    tag = mail._new_tag().decode()
    mail.send(f"{tag} IDLE\r\n".encode())
    # Server should respond with "+ idling"
    resp = mail.readline()
    if b"+" not in resp:
        # IDLE not supported, fall back
        return False

    # Wait for EXISTS / RECENT or timeout
    import select
    sock = mail.socket()
    ready = select.select([sock], [], [], timeout)
    # Send DONE regardless
    mail.send(b"DONE\r\n")
    # Read the tagged response to complete the IDLE command
    while True:
        line = mail.readline()
        if line.startswith(tag.encode()):
            break
    return bool(ready[0])


def capture_confirmation_email(
    application_email: str,
    max_wait_seconds: int = 600,
    skip_subjects: list[str] | None = None,
) -> dict | None:
    """Keep an IMAP connection open waiting for the confirmation email.

    Stays connected and uses IDLE to wait for new mail from the server.
    Skips emails whose subject contains any of the skip_subjects strings.
    Only returns when the right email arrives or max_wait_seconds expires.

    Args:
        skip_subjects: list of lowercase substrings to skip (e.g. ["security code"])

    Returns the email dict if found, None otherwise.
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.warning("IMAP credentials not configured, skipping email capture")
        return None

    deadline = time.time() + max_wait_seconds
    app_email_lower = application_email.lower()
    skip_subjects = skip_subjects or []

    logger.info(f"Waiting for confirmation email to {application_email} (up to {max_wait_seconds}s)…")

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            # Check any unseen emails already in the inbox
            result = _check_unseen(mail, app_email_lower, skip_subjects, application_email)
            if result:
                logger.info(
                    f"Captured confirmation email for {application_email}: "
                    f"'{result['subject'][:60]}'"
                )
                _store_confirmation_email(result)
                return result

            # Wait for the server to signal new mail via IDLE
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            wait_secs = min(remaining, 120)  # re-check every 120s max (IDLE spec)
            logger.debug(f"IDLE waiting up to {wait_secs:.0f}s for new mail…")
            try:
                _idle_wait(mail, wait_secs)
            except Exception as e:
                logger.debug(f"IDLE error: {e}, reconnecting…")
                try:
                    mail.logout()
                except Exception:
                    pass
                mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
                mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                mail.select("INBOX")

    except Exception as e:
        logger.warning(f"Email capture error: {e}")
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass

    logger.info(
        f"No confirmation email for {application_email} "
        f"within {max_wait_seconds}s"
    )
    return None


def _store_confirmation_email(em: dict):
    """Store a captured confirmation email in the emails table."""
    conn = get_connection()
    to_addr = em.get("to_address", "")

    # Match to job by email_used
    job_id = match_email_to_job(to_addr)
    if not job_id:
        job_id = match_email_by_tag(to_addr)

    conn.execute(
        """INSERT INTO emails (job_id, from_address, to_address, subject,
           body_preview, email_type, received_date)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id, em.get("from_address", ""), to_addr,
            em.get("subject", ""), em.get("body_preview", "")[:500],
            "confirmation", em.get("date"),
        ),
    )
    conn.commit()
    conn.close()
    logger.info(f"Stored confirmation email for job_id={job_id}")
