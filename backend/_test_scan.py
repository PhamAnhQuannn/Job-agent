"""Scan-only test: open a Greenhouse application, run Phase 1 (SCAN),
print all discovered fields and their options, then close without filling."""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
os.environ["DRY_RUN"] = "true"
os.environ["HEADLESS"] = "false"

from database import get_connection
from automation.browser import create_browser, random_delay
from automation.adapters.greenhouse import GreenhouseAdapter

adapter = GreenhouseAdapter()


async def scan_form(job_url: str):
    """Navigate to a Greenhouse URL and scan all fields."""
    browser, context = await create_browser()
    try:
        page = await context.new_page()
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        await random_delay(1500, 2500)

        # Click "Apply" if on the description page
        apply_btn = page.locator('a:has-text("Apply"), button:has-text("Apply")')
        if await apply_btn.count() > 0:
            try:
                await apply_btn.first.click()
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                print(">> Apply click/load timed out, continuing anyway")
            await random_delay(1500, 2500)

        # Detect iframe
        form_page = page
        gh_iframe = page.frame_locator(
            'iframe[src*="boards.greenhouse.io"], iframe[id*="grnhse"]'
        )
        try:
            iframe_name = gh_iframe.locator('#first_name, #applicant_name')
            if await iframe_name.count() > 0:
                for frame in page.frames:
                    if "greenhouse" in (frame.url or ""):
                        form_page = frame
                        print(">> Switched to Greenhouse iframe")
                        break
        except Exception:
            pass

        # Phase 1: SCAN (use _scan_form_fields — the active method)
        fields = await adapter._scan_form_fields(form_page)

        print(f"\n{'='*80}")
        print(f"SCAN RESULT: {len(fields)} fields found")
        print(f"URL: {job_url}")
        print(f"{'='*80}\n")

        for i, f in enumerate(fields, 1):
            ftype = f.get('ftype', f.get('role') or f.get('input_type') or f['tag'])
            print(f"  [{i:2d}] {ftype:10} | id={f['field_id'][:30]:30} | "
                  f"label='{f['label'][:50]}'")
            if f.get('options'):
                for opt in f['options'][:10]:
                    print(f"       -> {opt}")
                if len(f['options']) > 10:
                    print(f"       ... +{len(f['options'])-10} more")
            if f.get('current_value'):
                print(f"       (pre-filled: '{f['current_value'][:40]}')")
            if f.get('is_conditional'):
                print(f"       ** CONDITIONAL follow-up **")

        # Also dump as JSON for easy inspection
        json_path = os.path.join(os.path.dirname(__file__), "data", "screenshots", "last_scan.json")
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fp:
            json.dump(fields, fp, indent=2, ensure_ascii=False)
        print(f"\nFull scan saved to: {json_path}")

        # Keep browser open for manual inspection
        print("\nPress Enter to close the browser...")
        await asyncio.get_event_loop().run_in_executor(None, input)

    finally:
        await browser.close()


async def main():
    conn = get_connection()

    # Use a specific job id from CLI arg, a URL, or pick the first AUTO_APPLY greenhouse job
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith("http"):
            # Direct URL passed
            print(f"URL: {arg}\n")
            await scan_form(arg)
            return
        job_id = int(arg)
        row = conn.execute(
            "SELECT id, company, title, source_url FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT id, company, title, source_url FROM jobs
               WHERE source_url LIKE '%greenhouse%'
                 AND status IN ('AUTO_APPLY', 'SAVED', 'NEW')
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
    conn.close()

    if not row:
        print("No Greenhouse job found. Pass a job id: python _test_scan.py <id>")
        return

    job = dict(row)
    print(f"Job #{job['id']}: {job['company']} — {job['title']}")
    print(f"URL: {job['source_url']}\n")

    await scan_form(job["source_url"])


asyncio.run(main())
