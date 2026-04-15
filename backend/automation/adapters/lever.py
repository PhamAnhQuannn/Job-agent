"""Lever ATS adapter — fill and submit application forms."""

import os
import logging
from playwright.async_api import Page, TimeoutError as PwTimeout

from automation.browser import (
    create_browser, take_screenshot, human_type, human_click,
    random_delay, DRY_RUN,
)
from automation.adapters.base import ATSAdapter, ApplyResult

logger = logging.getLogger(__name__)


class LeverAdapter(ATSAdapter):
    platform_name = "lever"

    async def apply(
        self,
        job_url: str,
        job_id: int,
        profile: dict,
        resume_path: str,
        cover_letter_path: str | None = None,
        answers: dict | None = None,
        company: str = "",
        location: str = "",
        job_title: str = "",
    ) -> ApplyResult:
        browser = None
        try:
            browser, context = await create_browser()
            page = await context.new_page()

            # Navigate to job page
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(1000, 2000)

            # Click "Apply" button on Lever job page
            apply_btn = page.locator('a.postings-btn, a:has-text("Apply"), button:has-text("Apply")')
            if await apply_btn.count() > 0:
                await apply_btn.first.click()
                await page.wait_for_load_state("domcontentloaded")
                await random_delay(1000, 2000)

            # Lever application form fields
            await self._fill_field(page, 'input[name="name"]', profile.get("full_name", ""))
            await self._fill_field(page, 'input[name="email"]', profile.get("email", ""))
            await self._fill_field(page, 'input[name="phone"]', profile.get("phone", ""))

            # Current company / school
            org_field = page.locator('input[name="org"], input[name="current_company"]')
            if await org_field.count() > 0:
                await self._fill_locator(page, org_field.first, profile.get("school", ""))

            # LinkedIn
            linkedin_field = page.locator('input[name="urls[LinkedIn]"], input[name*="linkedin"]')
            if await linkedin_field.count() > 0:
                await self._fill_locator(page, linkedin_field.first, profile.get("linkedin", ""))

            # GitHub / Portfolio
            github_field = page.locator('input[name="urls[GitHub]"], input[name*="github"]')
            if await github_field.count() > 0:
                await self._fill_locator(page, github_field.first, profile.get("github", ""))

            portfolio_field = page.locator('input[name="urls[Portfolio]"], input[name*="portfolio"], input[name*="website"]')
            if await portfolio_field.count() > 0:
                await self._fill_locator(page, portfolio_field.first, profile.get("portfolio", ""))

            # Upload resume
            resume_input = page.locator('input[type="file"][name="resume"], input[type="file"]:first-of-type')
            if await resume_input.count() > 0 and os.path.exists(resume_path):
                await resume_input.first.set_input_files(resume_path)
                await random_delay(1000, 2000)

            # Cover letter (Lever sometimes has a text area)
            if cover_letter_path and os.path.exists(cover_letter_path):
                cl_input = page.locator('input[type="file"][name*="cover"]')
                if await cl_input.count() > 0:
                    await cl_input.first.set_input_files(cover_letter_path)
                    await random_delay(1000, 2000)

            # Handle additional questions
            if answers:
                await self._fill_custom_questions(page, answers, company, job_title)

            if DRY_RUN:
                logger.info(f"DRY_RUN: Would submit Lever application for job {job_id}")
                return ApplyResult(
                    success=True, failure_step="dry_run"
                )

            # Submit
            submit_btn = page.locator(
                'button[type="submit"], button:has-text("Submit application"), '
                'button:has-text("Submit"), input[type="submit"]'
            )
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
                await random_delay(2000, 4000)

                confirmation = page.locator(
                    'text="Thank you", text="Application submitted", text="received", '
                    'text="application has been", .application-confirmation'
                )
                try:
                    await confirmation.first.wait_for(timeout=10000)
                    screenshot = await take_screenshot(page, company, location)
                    return ApplyResult(success=True, screenshot_path=screenshot)
                except PwTimeout:
                    return ApplyResult(
                        success=True,
                        failure_step="confirmation_uncertain",
                    )
            else:
                return ApplyResult(
                    success=False,
                    failure_step="no_submit_button",
                    error_message="Could not find submit button",
                )

        except Exception as e:
            logger.error(f"Lever apply error for job {job_id}: {e}")
            return ApplyResult(
                success=False,
                failure_step="exception",
                error_message=str(e)[:500],
            )
        finally:
            if browser:
                await browser.close()

    async def _fill_field(self, page: Page, selector: str, value: str):
        if not value:
            return
        try:
            field = page.locator(selector)
            if await field.count() > 0:
                await human_type(page, selector, value)
        except Exception as e:
            logger.debug(f"Could not fill {selector}: {e}")

    async def _fill_locator(self, page: Page, locator, value: str):
        if not value:
            return
        try:
            await locator.click()
            await random_delay(200, 400)
            await locator.fill(value)
            await random_delay(300, 600)
        except Exception as e:
            logger.debug(f"Could not fill locator: {e}")

    async def _fill_custom_questions(self, page: Page, answers: dict, company: str = "", job_title: str = ""):
        """Match Lever's custom question cards."""
        cards = await page.locator(".application-question, .custom-question, label").all()
        for card in cards:
            text = (await card.inner_text()).strip()
            if len(text) < 3:
                continue
            text_lower = text.lower()

            # Find the longest matching pattern (most specific wins)
            best_answer = None
            best_len = 0
            for pattern, answer in answers.items():
                if pattern.lower() in text_lower and len(pattern) > best_len:
                    best_answer = answer
                    best_len = len(pattern)

            # If no match found, use AI to generate answer
            if best_answer is None:
                # Only trigger AI if the card has a fillable input
                has_input = (
                    await card.locator("textarea").count() > 0
                    or await card.locator("input[type='text']").count() > 0
                    or await card.locator("select").count() > 0
                )
                if not has_input:
                    continue
                try:
                    from services.ai_writer import generate_answer
                    best_answer = await generate_answer(text, company=company, role_title=job_title)
                    from database import get_connection
                    conn = get_connection()
                    conn.execute(
                        "INSERT INTO answer_bank (question_pattern, answer, category) VALUES (?, ?, ?)",
                        (text_lower, best_answer, "ai_generated"),
                    )
                    conn.commit()
                    conn.close()
                    answers[text_lower] = best_answer
                    logger.info(f"AI auto-answered and saved: '{text[:50]}' -> '{best_answer[:50]}'")
                except Exception as e:
                    logger.warning(f"AI auto-answer failed for '{text[:50]}': {e}")
                    continue

            if not best_answer:
                continue

            # Try textarea first, then input, then select
            textarea = card.locator("textarea")
            if await textarea.count() > 0:
                await textarea.first.fill(best_answer)
                await random_delay(300, 600)
                continue
            inp = card.locator("input[type='text']")
            if await inp.count() > 0:
                await inp.first.fill(best_answer)
                await random_delay(300, 600)
                continue
            sel = card.locator("select")
            if await sel.count() > 0:
                await sel.first.select_option(label=best_answer)
                await random_delay(300, 600)
                continue
