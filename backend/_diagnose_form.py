"""Diagnose all form fields on a Greenhouse page to see what the bot sees."""
import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
os.environ["DRY_RUN"] = "true"
os.environ["HEADLESS"] = "false"

async def main():
    from automation.browser import create_browser, random_delay

    browser, context = await create_browser()
    page = await context.new_page()

    url = "https://job-boards.greenhouse.io/zscaler/jobs/5103680007"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await random_delay(2000, 3000)

    # Click Apply if needed
    apply_btn = page.locator('a:has-text("Apply"), button:has-text("Apply")')
    if await apply_btn.count() > 0:
        await apply_btn.first.click()
        await page.wait_for_load_state("domcontentloaded")
        await random_delay(2000, 3000)

    # 1. All labels with for attributes
    print("=" * 80)
    print("LABELS WITH 'for' ATTRIBUTE:")
    print("=" * 80)
    labels = await page.locator("label").all()
    for label in labels:
        text = (await label.inner_text()).strip()
        for_attr = await label.get_attribute("for")
        if for_attr:
            field = page.locator(f'[id="{for_attr}"]')
            count = await field.count()
            if count > 0:
                tag = await field.first.evaluate("el => el.tagName")
                input_type = ""
                if tag == "INPUT":
                    input_type = await field.first.get_attribute("type") or "text"
                print(f"  LABEL: {text[:60]:60s} | for={for_attr[:40]:40s} | tag={tag} type={input_type}")
            else:
                print(f"  LABEL: {text[:60]:60s} | for={for_attr[:40]:40s} | FIELD NOT FOUND")
        else:
            print(f"  LABEL: {text[:60]:60s} | NO 'for' ATTRIBUTE")

    # 2. All inputs/selects/textareas
    print()
    print("=" * 80)
    print("ALL FORM FIELDS (input/select/textarea):")
    print("=" * 80)
    fields = await page.locator("input, select, textarea").all()
    for f in fields:
        tag = await f.evaluate("el => el.tagName")
        field_id = await f.get_attribute("id") or ""
        name = await f.get_attribute("name") or ""
        field_type = await f.get_attribute("type") or ""
        aria_label = await f.get_attribute("aria-label") or ""
        placeholder = await f.get_attribute("placeholder") or ""
        required = await f.get_attribute("aria-required") or await f.get_attribute("required")
        value = ""
        try:
            value = await f.input_value()
        except:
            pass

        if field_type in ("hidden",):
            continue

        print(f"  {tag:8s} | id={field_id[:35]:35s} | name={name[:25]:25s} | type={field_type:10s} | aria={aria_label[:30]:30s} | val={value[:20]}")

    # 3. Check for ARIA listbox/combobox dropdowns
    print()
    print("=" * 80)
    print("ARIA LISTBOX/COMBOBOX ELEMENTS:")
    print("=" * 80)
    listboxes = await page.locator('[role="listbox"], [role="combobox"], [aria-haspopup="listbox"]').all()
    for lb in listboxes:
        lb_id = await lb.get_attribute("id") or ""
        role = await lb.get_attribute("role") or ""
        aria_label = await lb.get_attribute("aria-label") or ""
        text = (await lb.inner_text()).strip()[:60]
        print(f"  role={role:10s} | id={lb_id[:30]:30s} | aria={aria_label[:30]:30s} | text={text}")

    # 4. Education section
    print()
    print("=" * 80)
    print("EDUCATION SECTION FIELDS:")
    print("=" * 80)
    edu_fields = await page.locator('[id*="school"], [id*="degree"], [id*="discipline"], [id*="education"], [id*="start"], [id*="end"], [name*="school"], [name*="degree"]').all()
    for f in edu_fields:
        tag = await f.evaluate("el => el.tagName")
        field_id = await f.get_attribute("id") or ""
        name = await f.get_attribute("name") or ""
        field_type = await f.get_attribute("type") or ""
        aria_label = await f.get_attribute("aria-label") or ""
        print(f"  {tag:8s} | id={field_id[:40]:40s} | name={name[:25]:25s} | type={field_type:10s} | aria={aria_label[:40]}")

    await browser.close()

asyncio.run(main())
