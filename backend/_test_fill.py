"""Automated Greenhouse form fill (DRY_RUN — no submit).

Single flow: open browser → fill basics → scan → map → fill → re-scan dynamic → done.

Usage:
    python _test_fill.py https://job-boards.greenhouse.io/zscaler/jobs/5103680007
    python _test_fill.py https://job-boards.greenhouse.io/anduril/jobs/69415
"""
import asyncio
import json
import logging
import os
import re
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
# DRY_RUN and HEADLESS can be set via env vars before running
if "DRY_RUN" not in os.environ:
    os.environ["DRY_RUN"] = "true"
if "HEADLESS" not in os.environ:
    os.environ["HEADLESS"] = "false"

from database import get_connection
from services.email_manager import generate_email
from automation.browser import create_browser, random_delay
from automation.adapters.greenhouse import GreenhouseAdapter


def load_profile() -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM profile LIMIT 1").fetchone()
    conn.close()
    if not row:
        raise RuntimeError("No profile in DB")
    p = dict(row)
    parts = (p.get("full_name") or "").split()
    p["first_name"] = parts[0] if parts else ""
    p["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
    return p


def load_answers() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT question_pattern, answer FROM answer_bank").fetchall()
    conn.close()
    return {r["question_pattern"]: r["answer"] for r in rows}


def find_resume() -> str:
    for d in ["data/resumes", "../data/resumes"]:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".pdf"):
                    return os.path.abspath(os.path.join(d, f))
    return ""


def extract_company(url: str) -> str:
    """Extract company name from Greenhouse URL."""
    m = re.search(r"greenhouse\.io/(\w+)", url)
    return m.group(1) if m else "unknown"


async def fill_form(job_url: str):
    profile = load_profile()
    answers = load_answers()
    resume_path = find_resume()
    company = extract_company(job_url)
    catchall_email = generate_email(company)

    print("=" * 70)
    print("FILL PLAN")
    print("=" * 70)
    print(f"  Name:    {profile['first_name']} {profile['last_name']}")
    print(f"  Email:   {catchall_email}  (catch-all)")
    print(f"  Phone:   {profile.get('phone', '')}")
    print(f"  Resume:  {resume_path or '(none)'}")
    print(f"  Answers: {len(answers)} entries")
    print(f"  URL:     {job_url}")
    print("=" * 70)
    print()

    adapter = GreenhouseAdapter()
    browser, context = await create_browser()

    try:
        page = await context.new_page()
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        await random_delay(1500, 2500)

        # ── CHECK FOR DEAD / EXPIRED PAGE ─────────────────────
        page_text = (await page.locator("body").inner_text()).lower()
        if any(phrase in page_text for phrase in [
            "page not found",
            "no longer active",
            "no longer available",
            "position has been filled",
            "job has been closed",
            "this job is no longer",
            "404",
        ]):
            print("✗ Job page is dead or expired:")
            print(f"  {page_text.strip()[:200]}")
            return

        # Click "Apply" if on the description page
        apply_btn = page.locator('a:has-text("Apply"), button:has-text("Apply")')
        if await apply_btn.count() > 0:
            try:
                await apply_btn.first.click()
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                print(">> Apply click/load timed out, continuing")
            await random_delay(1500, 2500)

        # Detect iframe
        form_page = page
        try:
            gh_iframe = page.frame_locator(
                'iframe[src*="boards.greenhouse.io"], iframe[id*="grnhse"]'
            )
            iframe_el = gh_iframe.locator("#first_name, #applicant_name")
            if await iframe_el.count() > 0:
                for frame in page.frames:
                    if "greenhouse" in (frame.url or ""):
                        form_page = frame
                        print(">> Switched to Greenhouse iframe")
                        break
        except Exception:
            pass

        # ── BASIC FIELDS ────────────────────────────────────────
        print("--- Filling basic fields ---")

        await form_page.locator("#first_name").fill(profile["first_name"])
        print(f"  First Name: {profile['first_name']}")
        await random_delay(300, 500)

        await form_page.locator("#last_name").fill(profile["last_name"])
        print(f"  Last Name:  {profile['last_name']}")
        await random_delay(300, 500)

        # CATCH-ALL email (not personal!)
        await form_page.locator("#email").fill(catchall_email)
        print(f"  Email:      {catchall_email}")
        await random_delay(300, 500)

        await form_page.locator("#phone").fill(profile.get("phone", ""))
        print(f"  Phone:      {profile.get('phone', '')}")
        await random_delay(300, 500)

        # Resume upload
        if resume_path and os.path.exists(resume_path):
            resume_input = form_page.locator(
                'input[type="file"][id*="resume"], input[type="file"]:first-of-type'
            )
            if await resume_input.count() > 0:
                await resume_input.first.set_input_files(resume_path)
                print(f"  Resume:     {os.path.basename(resume_path)}")
                await random_delay(1000, 2000)
        else:
            print("  Resume:     (none, skipping)")

        # Education dates
        await adapter._fill_education_dates(form_page)

        # Override email in answer bank so custom-question scan uses catch-all
        answers["email"] = catchall_email

        # ── CUSTOM QUESTIONS (3-phase: scan → map → fill) ────
        print("\n--- Scan + Map + Fill (unified) ---")
        await adapter._fill_custom_questions(
            form_page, answers,
            company=company, job_title=""
        )

        dry_run = os.environ.get("DRY_RUN", "true").lower() in ("true", "1", "yes")

        if dry_run:
            print()
            print("=" * 70)
            print("FILL COMPLETE  (DRY_RUN — form NOT submitted)")
            print("=" * 70)
            print("\nInspect the form in the browser.")
            print("Press Enter to close...")
            await asyncio.get_event_loop().run_in_executor(None, input)
        else:
            # Let the page settle after fills
            await random_delay(2000, 3000)

            # ── SUBMIT ────────────────────────────────────────
            print("\n--- Submitting application ---")
            submit_btn = form_page.locator(
                'button[type="submit"], input[type="submit"], '
                'button:has-text("Submit")'
            )
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
                print("  Clicked Submit button")

                # Wait a moment for the page to react
                await random_delay(3000, 5000)

                # ── CHECK FOR VERIFICATION CODE PAGE ──────────
                page_text = await form_page.locator("body").inner_text()
                has_verify_page = (
                    "verification code" in page_text.lower()
                    or "security code" in page_text.lower()
                )
                if has_verify_page:
                    print("  ⚡ Verification code page detected!")
                    print(f"  Waiting up to 5 min for verification code email to {catchall_email}...")

                    from services.email_manager import (
                        capture_confirmation_email,
                        extract_verification,
                    )

                    code = None
                    verification_email = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: capture_confirmation_email(catchall_email, 300),
                    )
                    if verification_email:
                        body = verification_email.get("full_body", "")
                        # Strip HTML tags for code extraction
                        plain = re.sub(r"<[^>]+>", " ", body)
                        plain = re.sub(r"\s+", " ", plain).strip()
                        result = extract_verification(plain)
                        if result and result["type"] == "code":
                            code = result["value"]
                            print(f"  ✓ Extracted code: {code}")
                        else:
                            # Fallback: grab any 8-char alphanumeric token from plain text
                            m = re.search(r"\b([A-Za-z0-9]{8})\b", plain)
                            if m:
                                code = m.group(1)
                                print(f"  ✓ Fallback extracted code: {code}")
                            else:
                                print(f"  ⚠ Could not extract code from email body")
                                print(f"    Plain text: {plain[:400]}")
                    else:
                        print("  ⚠ No verification email within 5 min — skipping verification & confirmation")

                    if code:
                        # Fill the 8 security-code input boxes
                        code_inputs = form_page.locator(
                            'input[name*="security_code"], '
                            'input[aria-label*="code" i], '
                            'input[aria-label*="character" i], '
                            'input[autocomplete="one-time-code"], '
                            'input[type="text"][maxlength="1"]'
                        )
                        input_count = await code_inputs.count()

                        if input_count >= len(code):
                            for i, ch in enumerate(code):
                                await code_inputs.nth(i).fill(ch)
                                await random_delay(100, 200)
                            print(f"  ✓ Entered {len(code)}-char code into {input_count} fields")
                        elif input_count == 1:
                            # Single input that accepts the full code
                            await code_inputs.first.fill(code)
                            print(f"  ✓ Entered code into single input")
                        else:
                            # Try broader selector
                            all_inputs = form_page.locator(
                                'input[type="text"][maxlength="1"], '
                                'input[type="tel"][maxlength="1"], '
                                'input[inputmode="numeric"][maxlength="1"]'
                            )
                            cnt = await all_inputs.count()
                            if cnt >= len(code):
                                for i, ch in enumerate(code):
                                    await all_inputs.nth(i).fill(ch)
                                    await random_delay(100, 200)
                                print(f"  ✓ Entered code into {cnt} fields (broad selector)")
                            else:
                                print(f"  ⚠ Found {cnt} inputs but code is {len(code)} chars")

                        await random_delay(1000, 2000)

                        # Click the final "Submit application" button
                        final_submit = form_page.locator(
                            'button[type="submit"], '
                            'button:has-text("Submit application"), '
                            'button:has-text("Submit")'
                        )
                        if await final_submit.count() > 0:
                            await final_submit.first.click()
                            print("  Clicked final Submit button")
                        else:
                            print("  ⚠ No final submit button found")

                        # ── WAIT FOR CONFIRMATION EMAIL ───────────────
                        # Only wait if verification succeeded
                        from services.email_manager import capture_confirmation_email as cap_confirm
                        print(f"\n--- Waiting up to 5 min for confirmation email to {catchall_email} ---")
                        confirmation = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: cap_confirm(
                                catchall_email, 300,
                                skip_subjects=["security code"],
                            ),
                        )
                        if confirmation:
                            print(f"  ✓ Confirmation email received!")
                            print(f"    From:    {confirmation.get('from_address', '')}")
                            print(f"    Subject: {confirmation.get('subject', '')}")
                            plain_preview = re.sub(r"<[^>]+>", " ", confirmation.get("body_preview", ""))
                            plain_preview = re.sub(r"\s+", " ", plain_preview).strip()
                            print(f"    Preview: {plain_preview[:200]}")
                        else:
                            print("  ⚠ No confirmation email within 5 min, moving on")
                else:
                    # No verification page — wait for confirmation directly
                    from services.email_manager import capture_confirmation_email as cap_confirm2
                    print(f"\n--- Waiting up to 5 min for confirmation email to {catchall_email} ---")
                    confirmation = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: cap_confirm2(
                            catchall_email, 300,
                            skip_subjects=["security code"],
                        ),
                    )
                    if confirmation:
                        print(f"  ✓ Confirmation email received!")
                        print(f"    From:    {confirmation.get('from_address', '')}")
                        print(f"    Subject: {confirmation.get('subject', '')}")
                        plain_preview = re.sub(r"<[^>]+>", " ", confirmation.get("body_preview", ""))
                        plain_preview = re.sub(r"\s+", " ", plain_preview).strip()
                        print(f"    Preview: {plain_preview[:200]}")
                    else:
                        print("  ⚠ No confirmation email within 5 min, moving on")
            else:
                print("  ✗ No submit button found!")

            print()
            print("=" * 70)
            print("SUBMIT COMPLETE")
            print("=" * 70)
            print("\nPress Enter to close...")
            await asyncio.get_event_loop().run_in_executor(None, input)

    finally:
        await browser.close()


async def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://job-boards.greenhouse.io/zscaler/jobs/5103680007"
    await fill_form(url)


if __name__ == "__main__":
    asyncio.run(main())
