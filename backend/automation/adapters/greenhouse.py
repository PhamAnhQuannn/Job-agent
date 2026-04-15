"""Greenhouse ATS adapter — fill and submit application forms.

Uses a multi-phase pipeline:
  Phase 1 – BASIC:    Fill standard fields (name, email, phone, uploads).
  Phase 2 – CUSTOM:   Scan → Map → Fill custom questions (with re-scan).
  Phase 3 – VERIFY:   Ensure all required fields are filled before submit.
  Phase 4 – SUBMIT:   Submit only when validation passes.
"""

import os
import re
import asyncio
import logging
from playwright.async_api import Page, TimeoutError as PwTimeout

from automation.browser import (
    create_browser, human_type, human_click,
    random_delay, DRY_RUN,
)
from automation.adapters.base import ATSAdapter, ApplyResult

logger = logging.getLogger(__name__)

# Field type constants
FTYPE_TEXT      = "text"
FTYPE_TEXTAREA  = "textarea"
FTYPE_NUMBER    = "number"
FTYPE_CHECKBOX  = "checkbox"
FTYPE_RADIO     = "radio"
FTYPE_SELECT    = "select"
FTYPE_COMBOBOX  = "combobox"     # ARIA combobox (dropdown + type)
FTYPE_FILE      = "file"
FTYPE_HIDDEN    = "hidden"

MAX_VERIFY_ATTEMPTS = 3


class GreenhouseAdapter(ATSAdapter):
    platform_name = "greenhouse"

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

            # ── CHECK FOR DEAD / EXPIRED PAGE ─────────────────
            page_text = (await page.locator("body").inner_text()).lower()
            dead_phrases = [
                "page not found",
                "no longer active",
                "no longer available",
                "position has been filled",
                "job has been closed",
                "this job is no longer",
                "404",
            ]
            if any(phrase in page_text for phrase in dead_phrases):
                logger.info(f"Job page is dead/expired: {job_url}")
                await browser.close()
                return ApplyResult(
                    success=False,
                    failure_step="page_dead",
                    error_message=page_text.strip()[:200],
                )

            # Click "Apply" button if on job description page
            apply_btn = page.locator('a:has-text("Apply"), button:has-text("Apply")')
            if await apply_btn.count() > 0:
                await apply_btn.first.click()
                await page.wait_for_load_state("domcontentloaded")
                await random_delay(1000, 2000)

            # Detect if Greenhouse form is inside an iframe (custom career pages)
            form_page = page
            gh_iframe = page.frame_locator('iframe[src*="boards.greenhouse.io"], iframe[id*="grnhse"]')
            # Check if the iframe contains the form
            try:
                iframe_name = gh_iframe.locator('#first_name, #applicant_name')
                if await iframe_name.count() > 0:
                    # Switch to iframe context
                    for frame in page.frames:
                        if "greenhouse" in (frame.url or ""):
                            form_page = frame
                            logger.info(f"Detected Greenhouse iframe, switching context")
                            break
            except Exception:
                pass  # No iframe, use main page

            # Fill basic fields
            await self._fill_field(form_page, "#first_name", profile.get("first_name", ""))
            await self._fill_field(form_page, "#last_name", profile.get("last_name", ""))
            await self._fill_field(form_page, "#email", profile.get("email", ""))
            await self._fill_field(form_page, "#phone", profile.get("phone", ""))

            # Select country code for phone (United States +1)
            country_select = form_page.locator('select[id*="country"], select[name*="country"]')
            if await country_select.count() > 0:
                try:
                    await country_select.first.select_option(label="United States")
                except Exception:
                    try:
                        await country_select.first.select_option(value="US")
                    except Exception as e:
                        logger.debug(f"Could not select country: {e}")
                await random_delay(300, 500)

            # LinkedIn/GitHub/Portfolio
            linkedin_field = form_page.locator('input[name*="linkedin"], input[id*="linkedin"]')
            if await linkedin_field.count() > 0:
                await self._fill_locator(form_page, linkedin_field.first, profile.get("linkedin", ""))

            github_field = form_page.locator('input[name*="github"], input[id*="github"], input[name*="website"]')
            if await github_field.count() > 0:
                await self._fill_locator(form_page, github_field.first, profile.get("github", ""))

            # Upload resume
            resume_input = form_page.locator('input[type="file"][id*="resume"], input[type="file"]:first-of-type')
            if await resume_input.count() > 0 and os.path.exists(resume_path):
                await resume_input.first.set_input_files(resume_path)
                await random_delay(1000, 2000)

            # Upload cover letter
            if cover_letter_path and os.path.exists(cover_letter_path):
                cl_input = form_page.locator('input[type="file"][id*="cover"], input[type="file"]:nth-of-type(2)')
                if await cl_input.count() > 0:
                    await cl_input.first.set_input_files(cover_letter_path)
                    await random_delay(1000, 2000)

            # Handle education date fields (split month/year number inputs)
            await self._fill_education_dates(form_page)

            # Handle custom questions from answer bank
            if answers:
                await self._fill_custom_questions(form_page, answers, company, job_title)

            # ── Verify all required fields are filled before submit ──
            for attempt in range(MAX_VERIFY_ATTEMPTS):
                await random_delay(500, 1000)
                unfilled = await self._get_unfilled_required_fields(form_page)
                if not unfilled:
                    logger.info(f"All required fields verified filled (attempt {attempt + 1})")
                    break
                logger.warning(
                    f"Verify attempt {attempt + 1}/{MAX_VERIFY_ATTEMPTS}: "
                    f"{len(unfilled)} required fields still empty: "
                    + ", ".join(f"'{u['label'][:30]}'" for u in unfilled[:5])
                )
                # Re-scan and try to fill the missing fields
                new_fields = await self._scan_form_fields(form_page)
                unfilled_ids = {u["field_id"] for u in unfilled if u["field_id"]}
                fields_to_fill = [
                    f for f in new_fields
                    if f["field_id"] in unfilled_ids or not f["current_value"]
                ]
                if fields_to_fill:
                    plan = await self._map_answers(
                        fields_to_fill, answers or {}, company, job_title
                    )
                    if plan:
                        await self._execute_fill_plan(form_page, plan)
            else:
                # Exhausted retries — check one final time
                unfilled = await self._get_unfilled_required_fields(form_page)
                if unfilled:
                    labels = [u["label"][:40] for u in unfilled[:5]]
                    logger.error(f"Cannot submit: required fields still empty: {labels}")
                    return ApplyResult(
                        success=False,
                        failure_step="required_fields_empty",
                        error_message=f"Required fields still empty after {MAX_VERIFY_ATTEMPTS} attempts: {labels}",
                    )

            # ── Submit ──
            if DRY_RUN:
                logger.info(f"DRY_RUN: Would submit application for job {job_id}")
                return ApplyResult(success=True, failure_step="dry_run")

            submit_btn = form_page.locator(
                'button[type="submit"], input[type="submit"], button:has-text("Submit")'
            )
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
                logger.info("Clicked Submit button")
                await random_delay(3000, 5000)

                # ── CHECK FOR VERIFICATION / SECURITY CODE PAGE ──
                page_text_after = await form_page.locator("body").inner_text()
                has_verify_page = (
                    "verification code" in page_text_after.lower()
                    or "security code" in page_text_after.lower()
                )

                if has_verify_page:
                    logger.info("Verification code page detected — waiting for email")
                    from services.email_manager import (
                        capture_confirmation_email,
                        extract_verification,
                    )
                    email_addr = profile.get("email", "")
                    loop = asyncio.get_event_loop()
                    verification_email = await loop.run_in_executor(
                        None,
                        lambda: capture_confirmation_email(email_addr, 300),
                    )

                    code = None
                    if verification_email:
                        body = verification_email.get("full_body", "")
                        plain = re.sub(r"<[^>]+>", " ", body)
                        plain = re.sub(r"\s+", " ", plain).strip()
                        result = extract_verification(plain)
                        if result and result["type"] == "code":
                            code = result["value"]
                        else:
                            m = re.search(r"\b([A-Za-z0-9]{8})\b", plain)
                            if m:
                                code = m.group(1)

                    if not code:
                        logger.warning("Could not get verification code — verification failed")
                        return ApplyResult(
                            success=False,
                            failure_step="verification_code_missing",
                            error_message="No verification code received within 5 min",
                        )

                    logger.info(f"Extracted verification code: {code}")

                    # Fill the security code input boxes
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
                    elif input_count == 1:
                        await code_inputs.first.fill(code)
                    else:
                        broad = form_page.locator(
                            'input[type="text"][maxlength="1"], '
                            'input[type="tel"][maxlength="1"], '
                            'input[inputmode="numeric"][maxlength="1"]'
                        )
                        cnt = await broad.count()
                        if cnt >= len(code):
                            for i, ch in enumerate(code):
                                await broad.nth(i).fill(ch)
                                await random_delay(100, 200)
                        else:
                            logger.warning(f"Found {cnt} code inputs but code is {len(code)} chars")

                    await random_delay(1000, 2000)

                    # Click the final "Submit application" button
                    final_submit = form_page.locator(
                        'button[type="submit"], '
                        'button:has-text("Submit application"), '
                        'button:has-text("Submit")'
                    )
                    if await final_submit.count() > 0:
                        await final_submit.first.click()
                        logger.info("Clicked final Submit after verification code")
                    else:
                        logger.warning("No final submit button found after code entry")

                    await random_delay(2000, 4000)

                # ── WAIT FOR CONFIRMATION EMAIL ──────────────────
                from services.email_manager import capture_confirmation_email as _cap
                email_addr = profile.get("email", "")
                loop = asyncio.get_event_loop()
                logger.info(f"Waiting up to 5 min for confirmation email to {email_addr}")
                confirmation = await loop.run_in_executor(
                    None,
                    lambda: _cap(email_addr, 300, skip_subjects=["security code", "verification"]),
                )
                if confirmation:
                    logger.info(
                        f"Application submitted successfully for job {job_id} "
                        f"(subject: {confirmation.get('subject', '')})"
                    )
                    return ApplyResult(success=True)
                else:
                    logger.warning(f"No confirmation email for job {job_id} — marking uncertain")
                    return ApplyResult(success=True, failure_step="confirmation_uncertain")
            else:
                return ApplyResult(
                    success=False,
                    failure_step="no_submit_button",
                    error_message="Could not find submit button",
                )

        except Exception as e:
            logger.error(f"Greenhouse apply error for job {job_id}: {e}")
            return ApplyResult(
                success=False,
                failure_step="exception",
                error_message=str(e)[:500],
            )
        finally:
            if browser:
                await browser.close()

    async def _fill_education_dates(self, page):
        """Fill structured education date fields (month/year number inputs)."""
        date_fields = {
            'input[id*="start-year"]': "2024",
            'input[id*="start-month"]': "1",
            'input[id*="end-year"]': "2026",
            'input[id*="end-month"]': "5",
        }
        for selector, value in date_fields.items():
            try:
                field = page.locator(selector)
                if await field.count() > 0:
                    await field.first.fill(value)
                    await random_delay(200, 400)
            except Exception as e:
                logger.debug(f"Could not fill education date {selector}: {e}")

    async def _fill_field(self, page: Page, selector: str, value: str):
        """Fill a field if it exists."""
        if not value:
            return
        try:
            field = page.locator(selector)
            if await field.count() > 0:
                await human_type(page, selector, value)
        except Exception as e:
            logger.debug(f"Could not fill {selector}: {e}")

    async def _fill_locator(self, page: Page, locator, value: str):
        """Fill a field using a locator."""
        if not value:
            return
        try:
            await locator.click()
            await random_delay(200, 400)
            await locator.fill(value)
            await random_delay(300, 600)
        except Exception as e:
            logger.debug(f"Could not fill locator: {e}")

    # ------------------------------------------------------------------
    # VERIFY: Ensure all required fields are filled before submit
    # ------------------------------------------------------------------

    async def _get_unfilled_required_fields(self, page: Page) -> list[dict]:
        """Scan for required fields that are still empty."""
        unfilled = []

        # Check fields with required / aria-required attributes
        required_locator = page.locator(
            '[required]:visible, [aria-required="true"]:visible'
        )
        seen_ids: set[str] = set()
        count = await required_locator.count()

        for i in range(count):
            field = required_locator.nth(i)
            try:
                tag = await field.evaluate("el => el.tagName")
                input_type = ""
                if tag == "INPUT":
                    input_type = (await field.get_attribute("type") or "text").lower()
                    if input_type in ("hidden", "submit"):
                        continue

                role = await field.get_attribute("role") or ""

                # Check if field has a value
                has_value = False
                if input_type == "checkbox":
                    has_value = await field.is_checked()
                elif input_type == "file":
                    file_count = await field.evaluate(
                        "el => el.files ? el.files.length : 0"
                    )
                    has_value = file_count > 0
                elif tag == "SELECT":
                    val = await field.evaluate(
                        "el => el.options[el.selectedIndex]"
                        " ? el.options[el.selectedIndex].value : ''"
                    )
                    has_value = bool(val and val.strip())
                elif role == "combobox":
                    # ARIA combobox: check aria-activedescendant or the
                    # displayed text in the parent's selected-value element
                    has_value = await field.evaluate("""el => {
                        // Check if a sibling/nearby element shows a selected value
                        const parent = el.closest('.select2-container, [class*="select"], [class*="combo"]')
                                     || el.parentElement;
                        if (parent) {
                            const chosen = parent.querySelector(
                                '.select2-selection__rendered, '
                                + '[class*="selected"], [class*="chosen"], '
                                + '[class*="single-value"]'
                            );
                            if (chosen && chosen.textContent.trim()) return true;
                        }
                        // Check aria-activedescendant (means an option was selected)
                        if (el.getAttribute('aria-activedescendant')) return true;
                        // Check input value
                        if (el.value && el.value.trim()) return true;
                        // Check if there's a hidden input sibling with value
                        const hidden = parent
                            ? parent.querySelector('input[type="hidden"]')
                            : null;
                        if (hidden && hidden.value && hidden.value.trim()) return true;
                        return false;
                    }""")
                else:
                    try:
                        val = (await field.input_value()).strip()
                        has_value = bool(val)
                    except Exception:
                        pass

                if has_value:
                    continue

                fid = await field.get_attribute("id") or ""
                if not fid or fid in seen_ids:
                    continue
                seen_ids.add(fid)

                label_text = ""
                if fid:
                    label = page.locator(f'label[for="{fid}"]')
                    if await label.count() > 0:
                        label_text = (await label.inner_text()).strip()

                unfilled.append({
                    "field_id": fid,
                    "label": label_text or fid or f"unknown-{i}",
                    "tag": tag,
                    "input_type": input_type,
                })
            except Exception as e:
                logger.debug(f"Error checking required field: {e}")

        # Also check labels containing asterisk (*) for visually-required fields
        try:
            labels = await page.locator("label").all()
            for label_el in labels:
                text = (await label_el.inner_text()).strip()
                if "*" not in text:
                    continue
                for_attr = await label_el.get_attribute("for")
                if not for_attr or for_attr in seen_ids:
                    continue
                field = page.locator(f'[id="{for_attr}"]')
                if await field.count() == 0 or not await field.is_visible():
                    continue

                role = await field.get_attribute("role") or ""
                has_value = False
                if role == "combobox":
                    has_value = await field.evaluate("""el => {
                        if (el.getAttribute('aria-activedescendant')) return true;
                        if (el.value && el.value.trim()) return true;
                        const parent = el.parentElement;
                        const hidden = parent
                            ? parent.querySelector('input[type="hidden"]')
                            : null;
                        if (hidden && hidden.value && hidden.value.trim()) return true;
                        return false;
                    }""")
                else:
                    try:
                        val = (await field.input_value()).strip()
                        has_value = bool(val)
                    except Exception:
                        pass
                if not has_value:
                    seen_ids.add(for_attr)
                    unfilled.append({
                        "field_id": for_attr,
                        "label": text,
                        "tag": await field.evaluate("el => el.tagName"),
                        "input_type": "",
                    })
        except Exception as e:
            logger.debug(f"Error checking asterisk-required fields: {e}")

        return unfilled

    # ------------------------------------------------------------------
    # 3-PHASE FORM FILLING: Scan → Map → Fill
    # ------------------------------------------------------------------

    async def _fill_custom_questions(self, page: Page, answers: dict, company: str = "", job_title: str = ""):
        """Incremental form filling with scan-map-fill loop.

        Flow: SCAN → MAP (with AI) → FILL one field → RE-SCAN → MAP → FILL next...
        This handles dynamic fields that only appear after filling previous fields.
        """
        filled_ids = set()
        max_iterations = 50  # Safety limit to prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            
            # ---------- SCAN ----------
            all_fields = await self._scan_form_fields(page)
            # Filter out already-filled fields
            new_fields = [
                f for f in all_fields
                if f["field_id"] not in filled_ids and not f["current_value"]
            ]
            
            if not new_fields:
                logger.info(f"Iteration {iteration}: No more fields to fill, done")
                break
            
            logger.info(f"Iteration {iteration}: SCAN found {len(new_fields)} unfilled fields")

            # ---------- MAP + AI ----------
            fill_plan = await self._map_answers(new_fields, answers, company, job_title)
            
            if not fill_plan:
                logger.info(f"Iteration {iteration}: MAP produced no fill plan, done")
                break
            
            logger.info(f"Iteration {iteration}: MAP created plan for {len(fill_plan)} fields")

            # ---------- FILL (one at a time with re-scan after each) ----------
            for entry in fill_plan:
                await self._fill_single_field(page, entry)
                filled_ids.add(entry["field_id"])
                
                # Small delay to let dynamic fields render
                await random_delay(300, 500)

            # After filling this batch, loop back to re-scan for new dynamic fields
        
        if iteration >= max_iterations:
            logger.warning(f"Reached max iterations ({max_iterations}), stopping fill loop")
        else:
            logger.info(f"Form filling completed after {iteration} iterations")

    # ── Phase 1: Scan ────────────────────────────────────────────────

    async def _scan_form_fields(self, page: Page) -> list[dict]:
        """Scan every label → field pair and gather metadata + options."""
        import re as _re
        fields: list[dict] = []
        labels = await page.locator("label").all()

        for label in labels:
            text = (await label.inner_text()).strip()
            if len(text) < 3:
                continue

            for_attr = await label.get_attribute("for")
            if not for_attr:
                continue

            field = page.locator(f'[id="{for_attr}"]')
            if await field.count() == 0:
                continue

            tag = await field.evaluate("el => el.tagName")
            input_type = ""
            if tag == "INPUT":
                input_type = (await field.get_attribute("type") or "text").lower()
                if input_type in ("file", "hidden", "submit"):
                    continue

            role = await field.get_attribute("role") or ""

            # Check current value
            current_value = ""
            try:
                if input_type == "checkbox":
                    # For checkboxes, check the actual checked state
                    is_checked = await field.is_checked()
                    current_value = "checked" if is_checked else ""
                else:
                    current_value = (await field.input_value()).strip()
            except Exception:
                pass

            # Detect conditional field patterns
            text_lower = text.lower()
            is_conditional = bool(_re.search(
                r"if you selected|if yes|if so|please specify|please advise|"
                r"please explain|please describe|please provide|"
                r"please tell us how",
                text_lower
            ))

            # For combobox: open dropdown, collect all options, close it
            options: list[str] = []
            if role == "combobox":
                options = await self._collect_combobox_options(page, field)
            elif tag == "SELECT":
                try:
                    opt_els = await field.locator("option").all()
                    for o in opt_els:
                        t = (await o.inner_text()).strip()
                        if t and t.lower() not in ("", "select", "select...",
                                                    "select one", "select a country",
                                                    "-- select --"):
                            options.append(t)
                except Exception:
                    pass

            entry = {
                "label": text,
                "field_id": for_attr,
                "tag": tag,
                "input_type": input_type,
                "role": role,
                "options": options,
                "current_value": current_value,
                "is_conditional": is_conditional,
            }
            fields.append(entry)
            logger.debug(f"Scanned: [{tag}/{role or input_type}] "
                         f"'{text[:50]}' opts={len(options)} "
                         f"cond={is_conditional} val='{current_value[:20]}'")

        return fields

    async def _collect_combobox_options(self, page: Page, field) -> list[str]:
        """Click a combobox open, read all role=option, close it."""
        options: list[str] = []
        try:
            await field.click()
            await random_delay(300, 500)
            try:
                await page.locator('[role="option"]:visible').first.wait_for(timeout=2000)
            except Exception:
                pass
            opt_els = await page.locator('[role="option"]:visible').all()
            for o in opt_els:
                t = (await o.inner_text()).strip()
                if t:
                    options.append(t)
            # Close the dropdown without selecting
            await page.keyboard.press("Escape")
            await random_delay(200, 300)
        except Exception as e:
            logger.debug(f"Could not collect combobox options: {e}")
        return options

    # ── Phase 2: Map ─────────────────────────────────────────────────

    async def _map_answers(
        self, fields: list[dict], answers: dict,
        company: str, job_title: str,
    ) -> list[dict]:
        """Build a fill plan: for each field decide the answer + chosen option.
        
        **KEY: ALL ANSWERS ARE RESOLVED HERE (from bank or AI)**
        
        Flow for each question:
        1. Try to match from answer bank (longest pattern wins)
        2. If no match → Call AI to generate answer
        3. Save AI answer to bank
        4. Return fill_plan with ALL VALUES READY
        
        The FILL phase just executes this plan - no AI calls during fill.
        
        This also handles:
        - Dropdown option resolution (pick best matching option)
        - Conditional field skipping (based on parent answer)
        """
        import re as _re
        fill_plan: list[dict] = []

        # Track the previous field's chosen value so we can decide
        # whether to skip conditional follow-ups.
        prev_chosen: str = ""

        for f in fields:
            label = f["label"]
            text_lower = label.lower()

            # Already has a value → skip
            if f["current_value"]:
                logger.debug(f"MAP skip (filled): '{label[:40]}' = '{f['current_value'][:30]}'")
                prev_chosen = f["current_value"].lower()
                continue

            # ── Conditional field check ──
            if f["is_conditional"]:
                # Skip if the parent answer was NOT "other" / "yes"
                trigger = prev_chosen.lower() if prev_chosen else ""
                should_fill = (
                    "other" in trigger
                    or trigger.startswith("yes")
                    or trigger == ""  # unknown parent → fill to be safe
                )
                if not should_fill:
                    logger.info(f"MAP skip (conditional): '{label[:50]}' "
                                f"(parent chose '{prev_chosen[:30]}')")
                    continue

            # ── Find best answer from bank (longest-match wins) ──
            best_answer = None
            best_len = 0
            for pattern, answer in answers.items():
                if pattern.lower() in text_lower and len(pattern) > best_len:
                    best_answer = answer
                    best_len = len(pattern)

            # ── Resolve answer value (bank or AI) ──
            # For dropdowns: need to pick actual option from dropdown
            # For text: just use the answer directly
            chosen_option = ""
            if f["options"]:
                # DROPDOWN: bank answer → alt bank → AI (with options list)
                # Try bank answer first
                if best_answer:
                    chosen_option = self._pick_best_option(
                        f["options"], best_answer
                    )
                    if chosen_option:
                        logger.info(f"MAP: '{label[:40]}' -> option '{chosen_option}' "
                                    f"(answer was '{best_answer[:30]}')")

                # Try alt answers from bank
                if not chosen_option and best_answer:
                    for pattern, alt_answer in answers.items():
                        if pattern.lower() in text_lower and alt_answer != best_answer:
                            alt_match = self._pick_best_option(
                                f["options"], alt_answer
                            )
                            if alt_match:
                                chosen_option = alt_match
                                logger.info(
                                    f"MAP: '{label[:40]}' -> option '{chosen_option}' "
                                    f"(via alt answer '{alt_answer[:30]}' "
                                    f"from pattern '{pattern[:30]}')"
                                )
                                break

                # AI fallback for dropdown: ask AI to pick from options
                if not chosen_option:
                    try:
                        from services.ai_writer import generate_answer
                        ai_answer = await generate_answer(
                            label, company=company, role_title=job_title,
                            options=f["options"],
                        )
                        chosen_option = self._pick_best_option(
                            f["options"], ai_answer
                        )
                        if chosen_option:
                            self._save_to_bank(answers, text_lower, chosen_option)
                            logger.info(f"MAP: '{label[:40]}' -> option '{chosen_option}' "
                                        f"(AI picked)")
                        else:
                            best_answer = ai_answer
                            self._save_to_bank(answers, text_lower, ai_answer)
                            logger.info(f"MAP: '{label[:40]}' -> no matching option, "
                                        f"will type AI answer '{ai_answer[:30]}'")
                    except Exception as e:
                        logger.warning(f"AI dropdown answer failed for '{label[:50]}': {e}")
                        if not best_answer:
                            continue
            else:
                # Text/checkbox field — AI fallback if no bank answer
                if best_answer is None:
                    try:
                        from services.ai_writer import generate_answer
                        best_answer = await generate_answer(
                            label, company=company, role_title=job_title,
                        )
                        self._save_to_bank(answers, text_lower, best_answer)
                        logger.info(f"AI answer saved: '{label[:50]}' -> "
                                    f"'{best_answer[:50]}'")
                    except Exception as e:
                        logger.warning(f"AI answer failed for '{label[:50]}': {e}")
                        continue

                if best_answer:
                    logger.info(f"MAP: '{label[:40]}' -> '{best_answer[:50]}'")

            if not best_answer and not chosen_option:
                continue

            # Add to fill plan with PRE-COMPUTED answer (no AI during fill)
            plan_entry = {
                **f,
                "answer": best_answer,
                "chosen_option": chosen_option,
            }
            fill_plan.append(plan_entry)
            # Track what we chose so the next field's conditional check works
            prev_chosen = chosen_option if chosen_option else best_answer

        return fill_plan  # ALL ANSWERS RESOLVED - ready to fill

    async def _fill_single_field(self, page: Page, entry: dict):
        """Fill a single field - answer is already resolved in MAP phase.
        
        Just executes the fill with the pre-computed answer.
        No AI calls here - all values come from the fill plan.
        """
        import re as _re
        label = entry["label"]
        fid = entry["field_id"]
        field = page.locator(f'[id="{fid}"]')
        tag = entry["tag"]
        role = entry["role"]
        input_type = entry["input_type"]
        answer = entry["answer"]
        chosen = entry["chosen_option"]

        try:
            if tag == "SELECT":
                await self._do_fill_select(field, label, answer, chosen)
            elif role == "combobox":
                await self._do_fill_combobox(page, field, label, chosen or answer)
            elif tag in ("INPUT", "TEXTAREA"):
                if input_type == "checkbox":
                    want_checked = answer.lower().strip() not in ("no", "false", "0", "")
                    is_checked = await field.is_checked()
                    if is_checked != want_checked:
                        try:
                            if want_checked:
                                await field.check(timeout=3000)
                            else:
                                await field.uncheck(timeout=3000)
                        except Exception:
                            # Fallback: click the label instead
                            try:
                                lbl = page.locator(f'label[for="{fid}"]')
                                await lbl.click(timeout=3000)
                            except Exception:
                                pass
                    logger.info(f"FILL CHECKBOX '{label[:40]}' -> '{answer}'")
                elif input_type == "radio":
                    await field.check()
                    logger.info(f"FILL RADIO '{label[:40]}' -> '{answer}'")
                elif input_type == "number":
                    nums = _re.findall(r'\d+', answer)
                    if nums:
                        year_nums = [n for n in nums if len(n) == 4]
                        val = year_nums[0] if year_nums else nums[0]
                        await field.fill(val)
                        logger.info(f"FILL NUMBER '{label[:40]}' -> '{val}'")
                else:
                    await field.fill(answer)
                    logger.info(f"FILL TEXT '{label[:40]}' -> '{answer[:50]}'")
        except Exception as e:
            logger.warning(f"FILL error '{label[:40]}': {e}")

        await random_delay(300, 600)

    @staticmethod
    def _save_to_bank(answers: dict, pattern: str, value: str):
        """Persist an AI-generated answer into the answer bank."""
        from database import get_connection
        conn = get_connection()
        conn.execute(
            "INSERT INTO answer_bank (question_pattern, answer, category) "
            "VALUES (?, ?, ?)",
            (pattern, value, "ai_generated"),
        )
        conn.commit()
        conn.close()
        answers[pattern] = value

    def _pick_best_option(self, options: list[str], answer: str) -> str:
        """Pick the best matching option from a list of available choices.

        Handles exact matches, yes/no intent, substring matches, and
        date/year proximity (e.g. answer 'May 2026' picks 'June 2026'
        from options).
        """
        import re as _re
        answer_lower = answer.lower().strip()

        # Detect yes/no intent
        yes_no = None
        if answer_lower.startswith("yes"):
            yes_no = "yes"
        elif answer_lower.startswith("no"):
            yes_no = "no"

        best_text = ""
        best_score = 0

        for opt in options:
            opt_lower = opt.lower().strip()

            # Exact match
            if opt_lower == answer_lower:
                return opt

            # Yes/No intent: prefer option that also starts with yes/no
            if yes_no and opt_lower.startswith(yes_no):
                score = 50 + len(opt_lower)
                if score > best_score:
                    best_text = opt
                    best_score = score
                continue

            # Substring match
            if answer_lower in opt_lower:
                score = len(answer_lower)
                if score > best_score:
                    best_text = opt
                    best_score = score
            elif opt_lower in answer_lower:
                score = len(opt_lower)
                if score > best_score:
                    best_text = opt
                    best_score = score

        if best_text:
            return best_text

        # ── Date proximity fallback ──
        # Parse a year (and optionally month) from the answer, then find
        # the closest option that also contains a year.
        _MONTHS = {
            "jan": 1, "january": 1, "feb": 2, "february": 2,
            "mar": 3, "march": 3, "apr": 4, "april": 4,
            "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "september": 9,
            "oct": 10, "october": 10, "nov": 11, "november": 11,
            "dec": 12, "december": 12,
        }

        def _parse_date_value(text: str) -> float | None:
            """Return a numeric year.month value (e.g. 2026.5) or None."""
            t = text.lower().strip()
            year_m = _re.search(r'\b(20\d{2})\b', t)
            if not year_m:
                return None
            year = int(year_m.group(1))
            # Also extract YYYY-MM format
            ym = _re.search(r'(20\d{2})-(\d{2})', t)
            if ym:
                return int(ym.group(1)) + int(ym.group(2)) / 12.0
            for mname, mnum in _MONTHS.items():
                if mname in t:
                    return year + mnum / 12.0
            return float(year)

        answer_date = _parse_date_value(answer)
        if answer_date is not None:
            closest_opt = ""
            closest_dist = float("inf")
            for opt in options:
                opt_date = _parse_date_value(opt)
                if opt_date is not None:
                    dist = abs(opt_date - answer_date)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest_opt = opt
            if closest_opt:
                return closest_opt

        # ── Year-only fallback ──
        # If answer contains a year, pick option with same year
        year_m = _re.search(r'\b(20\d{2})\b', answer_lower)
        if year_m:
            target_year = year_m.group(1)
            for opt in options:
                if target_year in opt:
                    return opt

        return ""

    # ── Phase 3: Fill ────────────────────────────────────────────────

    async def _execute_fill_plan(self, page: Page, plan: list[dict]):
        """Fill every field according to the pre-computed plan (batch mode)."""
        for entry in plan:
            await self._fill_single_field(page, entry)

    async def _do_fill_select(self, field, label: str, answer: str, chosen: str):
        """Fill a native <select> element."""
        target = chosen or answer
        try:
            await field.select_option(label=target)
            logger.info(f"FILL SELECT '{label[:40]}' -> '{target}'")
        except Exception:
            try:
                options = await field.locator("option").all()
                for opt in options:
                    opt_text = (await opt.inner_text()).strip()
                    if answer.lower() in opt_text.lower() or opt_text.lower() in answer.lower():
                        await field.select_option(label=opt_text)
                        logger.info(f"FILL SELECT '{label[:40]}' -> '{opt_text}' (partial)")
                        return
            except Exception as e:
                logger.warning(f"FILL SELECT failed '{label[:40]}': {e}")

    async def _do_fill_combobox(self, page: Page, field, label: str, value: str):
        """Select a value in an ARIA combobox dropdown."""
        try:
            # Open dropdown
            await field.click()
            await random_delay(300, 500)
            try:
                await page.locator('[role="option"]:visible').first.wait_for(timeout=2000)
            except Exception:
                pass

            # Try to click the matching option directly
            options = await page.locator('[role="option"]:visible').all()
            clicked = await self._click_matching_option(options, value)
            if clicked:
                logger.info(f"FILL COMBOBOX '{label[:40]}' -> '{clicked}'")
                return

            # Type to filter, then try again
            type_text = value.split(",")[0].split(".")[0].strip()[:20]
            await field.fill("")
            await field.type(type_text, delay=50)
            await random_delay(500, 800)

            options = await page.locator('[role="option"]:visible').all()
            clicked = await self._click_matching_option(options, value)
            if clicked:
                logger.info(f"FILL COMBOBOX '{label[:40]}' -> '{clicked}' (filtered)")
                return

            # No option matched — close and leave typed text
            await page.keyboard.press("Escape")
            logger.info(f"FILL COMBOBOX (typed) '{label[:40]}' -> '{type_text}'")
        except Exception as e:
            logger.warning(f"FILL COMBOBOX error '{label[:40]}': {e}")

    async def _click_matching_option(self, options, value: str) -> str:
        """Click the best matching option element, return its text or ''."""
        val_lower = value.lower().strip()

        # Detect yes/no intent
        yes_no = None
        if val_lower.startswith("yes"):
            yes_no = "yes"
        elif val_lower.startswith("no"):
            yes_no = "no"

        best_opt = None
        best_score = 0
        best_text = ""

        for opt in options:
            opt_text = (await opt.inner_text()).strip()
            opt_lower = opt_text.lower()

            if opt_lower == val_lower:
                await opt.click()
                return opt_text

            if yes_no and opt_lower.startswith(yes_no):
                score = 50 + len(opt_lower)
                if score > best_score:
                    best_opt, best_score, best_text = opt, score, opt_text
                continue

            if val_lower in opt_lower:
                score = len(val_lower)
                if score > best_score:
                    best_opt, best_score, best_text = opt, score, opt_text
            elif opt_lower in val_lower:
                score = len(opt_lower)
                if score > best_score:
                    best_opt, best_score, best_text = opt, score, opt_text

        if best_opt:
            await best_opt.click()
            return best_text
        return ""
