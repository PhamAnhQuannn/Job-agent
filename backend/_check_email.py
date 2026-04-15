"""Quick script to check IMAP for the Greenhouse verification code."""
import re
import imaplib
import email
import os
from dotenv import load_dotenv
from services.email_manager import extract_verification

load_dotenv(os.path.join("..", ".env"))

mail = imaplib.IMAP4_SSL(
    os.getenv("IMAP_SERVER", "imap.gmail.com"),
    int(os.getenv("IMAP_PORT", "993")),
)
mail.login(os.getenv("GMAIL_ADDRESS"), os.getenv("GMAIL_APP_PASSWORD"))
mail.select("INBOX")

status, ids = mail.search(None, "ALL")
all_ids = ids[0].split()[-10:]

for mid in reversed(all_ids):
    status, msg_data = mail.fetch(mid, "(RFC822)")
    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)
    subj = msg.get("Subject", "")
    to_addr = msg.get("To", "")
    from_addr = msg.get("From", "")

    if "zscaler" in to_addr.lower() or "security code" in subj.lower() or "verification" in subj.lower():
        print(f"Subject: {subj}")
        print(f"To: {to_addr}")
        print(f"From: {from_addr}")

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

        # Strip HTML
        plain = re.sub(r"<[^>]+>", " ", body)
        plain = re.sub(r"&\w+;", " ", plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        print(f"Body (plain): {plain[:600]}")
        print()

        result = extract_verification(plain)
        print(f"extract_verification result: {result}")

        m = re.search(r"\b([A-Za-z0-9]{8})\b", plain)
        if m:
            print(f"Fallback 8-char match: {m.group(1)}")
        print("---")

mail.logout()
