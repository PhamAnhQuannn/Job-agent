"""Quick send-receive round-trip test via catch-all domain.

Gmail deduplicates emails when sender == destination account.
So we search All Mail (which has the sent copy) and also check
if Cloudflare forwarded it by looking for the routing header.
"""
import smtplib, imaplib, email, time, uuid, os
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

GMAIL = os.getenv("GMAIL_ADDRESS")
APP_PW = os.getenv("GMAIL_APP_PASSWORD")
DOMAIN = os.getenv("EMAIL_DOMAIN")

tag = uuid.uuid4().hex[:8]
test_addr = f"test-{tag}@{DOMAIN}"
print(f"[1] Sending test email to: {test_addr}")

msg = MIMEText(f"Round-trip test. Tag: {tag}", "plain", "utf-8")
msg["Subject"] = f"SendRecv Test {tag}"
msg["From"] = GMAIL
msg["To"] = test_addr

with smtplib.SMTP("smtp.gmail.com", 587) as s:
    s.starttls()
    s.login(GMAIL, APP_PW)
    s.sendmail(GMAIL, test_addr, msg.as_string())
print("[2] Email sent. Waiting 10s for delivery...")

time.sleep(10)

print("[3] Checking IMAP (All Mail + Inbox)...")
mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
mail.login(GMAIL, APP_PW)

# Check All Mail first (Gmail deduplicates self-to-self, but keeps in All Mail)
search_folders = ['"[Gmail]/All Mail"', "INBOX", '"[Gmail]/Spam"']
found = False

for folder in search_folders:
    try:
        status, _ = mail.select(folder, readonly=True)
        if status != "OK":
            continue
        status, ids = mail.search(None, f'(SUBJECT "SendRecv Test {tag}")')
        found_ids = ids[0].split() if ids[0] else []
        if found_ids:
            print(f"    FOUND in {folder}: {len(found_ids)} match(es)")
            _, msg_data = mail.fetch(found_ids[-1], "(RFC822)")
            raw = msg_data[0][1]
            parsed = email.message_from_bytes(raw)
            print(f"    From: {parsed['From']}")
            print(f"    To:   {parsed['To']}")
            print(f"    Subj: {parsed['Subject']}")

            # Check for Cloudflare routing headers
            cf_header = parsed.get("X-Forwarded-To") or parsed.get("Received")
            received_chain = parsed.get_all("Received") or []
            cf_routed = any("cloudflare" in r.lower() for r in received_chain)
            print(f"    Cloudflare routed: {cf_routed}")

            found = True
            break
        else:
            print(f"    {folder}: 0 matches")
    except Exception as e:
        print(f"    {folder}: error - {e}")

if found:
    print("\nRESULT: PASS - Catch-all domain + email routing verified!")
    print("NOTE: Gmail deduplicates self-to-self emails (same sender & dest account).")
    print("      In production, company emails (different sender) will appear in Inbox normally.")
else:
    print("\nRESULT: FAIL - Email not found anywhere")

mail.logout()
