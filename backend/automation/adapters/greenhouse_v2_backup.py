"""Greenhouse ATS adapter — fill and submit application forms.

Uses a unified 3-phase pipeline for ALL fields (basic + custom):
  Phase 1 – SCAN:     Discover every field, its type, available dropdown options.
  Phase 2 – STRATEGY: Map each field to an answer, resolve dropdown choices,
                       skip conditional follow-ups when parent didn't trigger them.
  Phase 3 – FILL:     Execute the plan in order.
"""

import os
import re
import logging
from playwright.async_api import Page, TimeoutError as PwTimeout

from automation.browser import (
    create_browser, take_screenshot, human_type, human_click,
    random_delay, DRY_RUN,
)
from automation.adapters.base import ATSAdapter, ApplyResult

logger = logging.getLogger(__name__)

# Field type constants
FTYPE_TEXT     = "text"
FTYPE_TEXTAREA = "textarea"
FTYPE_NUMBER   = "number"
FTYPE_CHECKBOX = "checkbox"
FTYPE_RADIO    = "radio"
FTYPE_SELECT   = "select"
FTYPE_COMBOBOX = "combobox"   # ARIA combobox (dropdown + type)
FTYPE_FILE     = "file"
FTYPE_HIDDEN   = "hidden"


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

            # Click "Apply" button if on job description page
            apply_btn = page.locator('a:has-text("Apply"), button:has-text("Apply")')
            if await apply_btn.count() > 0:
                await apply_btn.first.click()
                await page.wait_for_load_state("domcontentloaded")
                await random_delay(1000, 2000)

            # Detect if Greenhouse form is inside an iframe
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
                            logger.info("Detected Greenhouse iframe, switching context")
                            break
            except Exception:
                pass

            # ── Build the full answer map (profile + answer bank) ──
            full_answers = self._build_answer_map(profile, answers or {})

            # ── Phase 1: SCAN ──
            fields = await self._scan_all_fields(form_page)
            logger.info(f"SCAN: found {len(fields)} fields")
            for f in fields:
                logger.debug(
                    f"  [{f['ftype']:10}] id={f['field_id'][:25]:25} "
                    f"label='{f['label'][:40]}' "
                    f"opts={len(f['options'])} "
                    f"val='{f['current_value'][:20]}' "
                    f"cond={f['is_conditional']}"
                )

            # ── Phase 2: STRATEGY ──
            plan = self._build_fill_strategy(fields, full_answers)
            logger.info(
                f"STRATEGY: "
                f"{sum(1 for p in plan if p['action']=='fill')} fill, "
                f"{sum(1 for p in plan if p['action']=='upload')} upload, "
                f"{sum(1 for p in plan if p['action']=='skip')} skip"
            )
            for p in plan:
                action = p["action"]
                if action == "skip":
                    logger.info(f"  SKIP  '{p['label'][:45]}' reason={p.get('reason','')}")
                elif action == "upload":
                    logger.info(f"  UPLOAD '{p['label'][:45]}'")
                else:
                    val = p.get("chosen_option") or p.get("answer", "")
                    logger.info(f"  FILL  [{p['ftype']:10}] '{p['label'][:35]}' -> '{val[:50]}'")

            # ── Phase 3: FILL ──
            await self._execute_plan(form_page, plan, resume_path)

            # ── Submit ──
            if DRY_RUN:
                logger.info(f"DRY_RUN: Would submit application for job {job_id}")
                return ApplyResult(success=True, failure_step="dry_run")

            submit_btn = form_page.locator(
                'button[type="submit"], input[type="submit"], '
                'button:has-text("Submit")'
            )
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
                await random_delay(2000, 4000)

                confirmation = page.locator(
                    'text=/thank you/i, text=/application submitted/i, '
                    'text=/received/i, text=/successfully/i, '
                    'text=/application has been/i'
                )
                try:
                    await confirmation.first.wait_for(timeout=10000)
                    screenshot = await take_screenshot(page, company, location)
                    return ApplyResult(success=True, screenshot_path=screenshot)
                except PwTimeout:
                    screenshot = await take_screenshot(page, company, location)
                    return ApplyResult(
                        success=True,
                        screenshot_path=screenshot,
                        failure_step="confirmation_uncertain",
                    )
            else:
                screenshot = await take_screenshot(page, company, location)
                return ApplyResult(
                    success=False,
                    failure_step="no_submit_button",
                    error_message="Could not find submit button",
                    screenshot_path=screenshot,
                )

        except Exception as e:
            logger.error(f"Greenhouse apply error for job {job_id}: {e}")
            return ApplyResult(
                success=False, failure_step="exception",
                error_message=str(e)[:500],
            )
        finally:
            if browser:
                await browser.close()

    # ==================================================================
    #  ANSWER MAP — merge profile data + answer bank into one lookup
    # ==================================================================

    def _build_answer_map(self, profile: dict, answers: dict) -> dict:
        """Merge profile fields and answer bank into a single dict
        keyed by lowercase pattern → answer value."""
        m: dict[str, str] = {}
        # Profile basics (match labels like "First Name", "Email", etc.)
        mapping = {
            "first name":  profile.get("first_name", ""),
            "last name":   profile.get("last_name", ""),
            "email":       profile.get("email", ""),
            "phone":       profile.get("phone", ""),
            "linkedin":    profile.get("linkedin", ""),
            "website":     profile.get("github", ""),
            "github":      profile.get("github", ""),
            "portfolio":   profile.get("github", ""),
        }
        for k, v in mapping.items():
            if v:
                m[k] = v
        # Answer bank entries (already lowercase-keyed)
        for k, v in answers.items():
            m[k.lower()] = v
        return m

    # ==================================================================
    #  Phase 1: SCAN — discover every field on the form
    # ==================================================================

    async def _scan_all_fields(self, page: Page) -> list[dict]:
        """Walk every <label>, resolve its field, classify type,
        collect dropdown options, detect conditional patterns."""
        fields: list[dict] = []
        seen_ids: set[str] = set()
        labels = await page.locator("label").all()

        for label_el in labels:
            text = (await label_el.inner_text()).strip()
            if len(text) < 2:
                continue

            for_attr = await label_el.get_attribute("for")
            if not for_attr or for_attr in seen_ids:
                continue
            seen_ids.add(for_attr)

            field = page.locator(f'[id="{for_attr}"]')
            if await field.count() == 0:
                continue

            tag = await field.evaluate("el => el.tagName")
            input_type = ""
            if tag == "INPUT":
                input_type = (await field.get_attribute("type") or "text").lower()
            role = await field.get_attribute("role") or ""

            # Classify field type
            if tag == "SELECT":
                ftype = FTYPE_SELECT
            elif role == "combobox":
                ftype = FTYPE_COMBOBOX
            elif tag == "TEXTAREA":
                ftype = FTYPE_TEXTAREA
            elif input_type == "file":
                ftype = FTYPE_FILE
            elif input_type in ("hidden", "submit"):
                continue  # skip
            elif input_type == "number":
                ftype = FTYPE_NUMBER
            elif input_type == "checkbox":
                ftype = FTYPE_CHECKBOX
            elif input_type == "radio":
                ftype = FTYPE_RADIO
            else:
                ftype = FTYPE_TEXT

            # Current value
            current_value = ""
            try:
                current_value = (await field.input_value()).strip()
            except Exception:
                pass

            # Conditional follow-up detection
            text_lower = text.lower()
            is_conditional = bool(re.search(
                r"if you selected|if yes|if so|please specify|please advise|"
                r"please explain|please describe|please provide details|"
                r"please tell us how",
                text_lower
            ))

            # Collect dropdown options
            options: list[str] = []
            if ftype == FTYPE_COMBOBOX:
                options = await self._collect_combobox_options(page, field)
            elif ftype == FTYPE_SELECT:
                options = await self._collect_select_options(field)

            fields.append({
                "label":          text,
                "field_id":       for_attr,
                "tag":            tag,
                "input_type":     input_type,
                "ftype":          ftype,
                "options":        options,
                "current_value":  current_value,
                "is_conditional": is_conditional,
            })

        # Also scan for education date fields (no labels, matched by id)
        for selector, value in {
            'input[id*="start-year"]':  "2024",
            'input[id*="start-month"]': "1",
            'input[id*="end-year"]':    "2026",
            'input[id*="end-month"]':   "5",
        }.items():
            try:
                f = page.locator(selector)
                if await f.count() > 0:
                    fid = await f.first.get_attribute("id") or selector
                    if fid not in seen_ids:
                        seen_ids.add(fid)
                        fields.append({
                            "label":          f"Education date ({fid})",
                            "field_id":       fid,
                            "tag":            "INPUT",
                            "input_type":     "number",
                            "ftype":          FTYPE_NUMBER,
                            "options":        [],
                            "current_value":  "",
                            "is_conditional": False,
                            "_edu_value":     value,
                        })
            except Exception:
                pass

        # Scan for file upload fields that may lack <label>
        file_inputs = await page.locator('input[type="file"]').all()
        for fi in file_inputs:
            fid = await fi.get_attribute("id") or ""
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                lbl = ""
                try:
                    parent = page.locator(f'[id="{fid}"]').locator("..")
                    lbl = (await parent.inner_text()).strip()[:60]
                except Exception:
                    pass
                fields.append({
                    "label":          lbl or f"File upload ({fid})",
                    "field_id":       fid,
                    "tag":            "INPUT",
                    "input_type":     "file",
                    "ftype":          FTYPE_FILE,
                    "options":        [],
                    "current_value":  "",
                    "is_conditional": False,
                })

        return fields

    async def _collect_combobox_options(self, page: Page, field) -> list[str]:
        """Click a combobox open, read all role=option, close it."""
        options: list[str] = []
        try:
            await field.click()
            await random_delay(300, 500)
            try:
                await page.locator('[role="option"]:visible').first.wait_for(
                    timeout=2000
                )
            except Exception:
                pass
            opt_els = await page.locator('[role="option"]:visible').all()
            for o in opt_els:
                t = (await o.inner_text()).strip()
                if t:
                    options.append(t)
            await page.keyboard.press("Escape")
            await random_delay(200, 300)
        except Exception as e:
            logger.debug(f"Could not collect combobox options: {e}")
        return options

    async def _collect_select_options(self, field) -> list[str]:
        """Read all <option> elements from a <select>."""
        options: list[str] = []
        skip = {"", "select", "select...", "select one",
                "select a country", "-- select --"}
        try:
            opt_els = await field.locator("option").all()
            for o in opt_els:
                t = (await o.inner_text()).strip()
                if t.lower() not in skip:
                    options.append(t)
        except Exception:
            pass
        return options

    # ==================================================================
    #  Phase 2: STRATEGY — decide what goes where before touching anything
    # ==================================================================

    def _build_fill_strategy(
        self, fields: list[dict], answers: dict
    ) -> list[dict]:
        """For each scanned field, decide: skip / fill / upload.
        Resolves dropdown answers to actual available options.
        Tracks parent choices to skip conditional follow-ups."""

        plan: list[dict] = []
        prev_chosen = ""  # tracks what the previous field resolved to

        for f in fields:
            entry = {**f, "action": "skip", "answer": "", "chosen_option": ""}
            label = f["label"]
            text_lower = label.lower()
            ftype = f["ftype"]

            # ── Already filled → skip ──
            if f["current_value"]:
                entry["reason"] = "already_filled"
                prev_chosen = f["current_value"]
                plan.append(entry)
                continue

            # ── File upload ──
            if ftype == FTYPE_FILE:
                fid_lower = f["field_id"].lower()
                if "cover" in fid_lower or "cover" in text_lower:
                    entry["reason"] = "cover_letter_skipped"
                    plan.append(entry)
                    continue
                entry["action"] = "upload"
                entry["file_path"] = "resume"
                plan.append(entry)
                continue

            # ── Education date (pre-set) ──
            if "_edu_value" in f:
                entry["action"] = "fill"
                entry["answer"] = f["_edu_value"]
                plan.append(entry)
                continue

            # ── Conditional follow-up check ──
            if f["is_conditional"]:
                trigger = prev_chosen.lower()
                should_fill = (
                    "other" in trigger
                    or trigger.startswith("yes")
                    or trigger == ""  # unknown parent → fill to be safe
                )
                if not should_fill:
                    entry["reason"] = f"parent='{prev_chosen[:30]}'"
                    plan.append(entry)
                    continue

            # ── Find best answer (longest-match wins) ──
            best_answer = None
            best_len = 0
            for pattern, answer in answers.items():
                if pattern.lower() in text_lower and len(pattern) > best_len:
                    best_answer = answer
                    best_len = len(pattern)

            if not best_answer:
                entry["reason"] = "no_answer"
                plan.append(entry)
                continue

            # ── Resolve dropdown choice ──
            chosen_option = ""
            if f["options"]:
                chosen_option = self._pick_best_option(f["options"], best_answer)

            entry["action"] = "fill"
            entry["answer"] = best_answer
            entry["chosen_option"] = chosen_option
            prev_chosen = chosen_option if chosen_option else best_answer
            plan.append(entry)

        return plan

    def _pick_best_option(self, options: list[str], answer: str) -> str:
        """Match answer text against available dropdown options."""
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

            if opt_lower == answer_lower:
                return opt

            if yes_no and opt_lower.startswith(yes_no):
                score = 50 + len(opt_lower)
                if score > best_score:
                    best_text, best_score = opt, score
                continue

            if answer_lower in opt_lower:
                score = len(answer_lower)
                if score > best_score:
                    best_text, best_score = opt, score
            elif opt_lower in answer_lower:
                score = len(opt_lower)
                if score > best_score:
                    best_text, best_score = opt, score

        return best_text

    # ==================================================================
    #  Phase 3: FILL — execute the strategy
    # ==================================================================

    async def _execute_plan(
        self, page: Page, plan: list[dict], resume_path: str
    ):
        """Walk the plan and fill each field."""
        for entry in plan:
            action = entry["action"]
            if action == "skip":
                continue

            label = entry["label"]
            fid = entry["field_id"]
            ftype = entry["ftype"]
            answer = entry.get("answer", "")
            chosen = entry.get("chosen_option", "")

            try:
                if action == "upload":
                    await self._do_upload(page, fid, resume_path)
                elif ftype == FTYPE_SELECT:
                    await self._do_fill_select(page, fid, label, answer, chosen)
                elif ftype == FTYPE_COMBOBOX:
                    await self._do_fill_combobox(
                        page, fid, label, chosen or answer
                    )
                elif ftype == FTYPE_CHECKBOX:
                    field = page.locator(f'[id="{fid}"]')
                    if answer.lower() in ("yes", "true", "1"):
                        await field.check()
                    else:
                        await field.uncheck()
                    logger.info(f"FILL CHECKBOX '{label[:40]}' -> '{answer}'")
                elif ftype == FTYPE_RADIO:
                    field = page.locator(f'[id="{fid}"]')
                    await field.check()
                    logger.info(f"FILL RADIO '{label[:40]}' -> '{answer}'")
                elif ftype == FTYPE_NUMBER:
                    field = page.locator(f'[id="{fid}"]')
                    nums = re.findall(r'\d+', answer)
                    if nums:
                        year_nums = [n for n in nums if len(n) == 4]
                        val = year_nums[0] if year_nums else nums[0]
                        await field.fill(val)
                        logger.info(f"FILL NUMBER '{label[:40]}' -> '{val}'")
                else:
                    # text / textarea — use .fill() for reliability
                    field = page.locator(f'[id="{fid}"]')
                    await field.fill("")
                    await field.fill(answer)
                    logger.info(f"FILL TEXT '{label[:40]}' -> '{answer[:50]}'")
            except Exception as e:
                logger.warning(f"FILL error '{label[:40]}': {e}")

            await random_delay(300, 600)

    # ── Fill helpers ─────────────────────────────────────────────────

    async def _do_upload(self, page: Page, fid: str, resume_path: str):
        """Upload a file to a file input."""
        if not os.path.exists(resume_path):
            logger.warning(f"Resume not found: {resume_path}")
            return
        field = page.locator(f'[id="{fid}"]')
        await field.set_input_files(resume_path)
        await random_delay(1000, 2000)
        logger.info(f"UPLOAD resume -> {fid}")

    async def _do_fill_select(
        self, page: Page, fid: str, label: str,
        answer: str, chosen: str
    ):
        """Fill a native <select>."""
        field = page.locator(f'[id="{fid}"]')
        target = chosen or answer
        try:
            await field.select_option(label=target)
            logger.info(f"FILL SELECT '{label[:40]}' -> '{target}'")
        except Exception:
            try:
                options = await field.locator("option").all()
                for opt in options:
                    opt_text = (await opt.inner_text()).strip()
                    if (answer.lower() in opt_text.lower()
                            or opt_text.lower() in answer.lower()):
                        await field.select_option(label=opt_text)
                        logger.info(
                            f"FILL SELECT '{label[:40]}' -> '{opt_text}' (partial)"
                        )
                        return
            except Exception as e:
                logger.warning(f"FILL SELECT failed '{label[:40]}': {e}")

    async def _do_fill_combobox(
        self, page: Page, fid: str, label: str, value: str
    ):
        """Select a value in an ARIA combobox dropdown."""
        field = page.locator(f'[id="{fid}"]')
        try:
            # Open dropdown
            await field.click()
            await random_delay(300, 500)
            try:
                await page.locator(
                    '[role="option"]:visible'
                ).first.wait_for(timeout=2000)
            except Exception:
                pass

            # Try to click matching option from visible list
            options = await page.locator('[role="option"]:visible').all()
            clicked = await self._click_matching_option(options, value)
            if clicked:
                logger.info(f"FILL COMBOBOX '{label[:40]}' -> '{clicked}'")
                return

            # Type to filter, then retry
            type_text = value.split(",")[0].split(".")[0].strip()[:20]
            await field.fill("")
            await field.type(type_text, delay=50)
            await random_delay(500, 800)

            options = await page.locator('[role="option"]:visible').all()
            clicked = await self._click_matching_option(options, value)
            if clicked:
                logger.info(
                    f"FILL COMBOBOX '{label[:40]}' -> '{clicked}' (filtered)"
                )
                return

            # No option matched — close dropdown, typed text stays
            await page.keyboard.press("Escape")
            logger.info(f"FILL COMBOBOX (typed) '{label[:40]}' -> '{type_text}'")
        except Exception as e:
            logger.warning(f"FILL COMBOBOX error '{label[:40]}': {e}")

    async def _click_matching_option(self, options, value: str) -> str:
        """Click the best matching visible option, return its text or ''."""
        val_lower = value.lower().strip()

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
"""Greenhouse ATS adapter — fill and submit application forms.

Uses a 3-phase pipeline:
  Phase 1 – SCAN:     Discover every field, its type, available dropdown options.
  Phase 2 – STRATEGY: Map each field to an answer, resolve dropdown choices,
                       skip conditional follow-ups when parent didn't trigger them.
  Phase 3 – FILL:     Execute the plan in order.
"""

import os
import re
import logging
from playwright.async_api import Page, TimeoutError as PwTimeout

from automation.browser import (
    create_browser, take_screenshot, human_type, human_click,
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

            # Submit
            if DRY_RUN:
                logger.info(f"DRY_RUN: Would submit application for job {job_id}")
                return ApplyResult(
                    success=True,
                    failure_step="dry_run",
                )

            submit_btn = form_page.locator('button[type="submit"], input[type="submit"], button:has-text("Submit")')
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
                await random_delay(2000, 4000)

                # Check for confirmation or error — use main page for confirmation
                # since some sites redirect out of iframe on submit
                confirmation = page.locator(
                    'text=/thank you/i, text=/application submitted/i, '
                    'text=/received/i, text=/successfully/i, text=/application has been/i'
                )
                try:
                    await confirmation.first.wait_for(timeout=10000)
                    screenshot = await take_screenshot(page, company, location)
                    return ApplyResult(success=True, screenshot_path=screenshot)
                except PwTimeout:
                    # Still take screenshot on uncertain confirmation
                    screenshot = await take_screenshot(page, company, location)
                    return ApplyResult(
                        success=True,
                        screenshot_path=screenshot,
                        failure_step="confirmation_uncertain",
                    )
            else:
                # Take a debug screenshot before reporting failure
                screenshot = await take_screenshot(page, company, location)
                return ApplyResult(
                    success=False,
                    failure_step="no_submit_button",
                    error_message="Could not find submit button",
                    screenshot_path=screenshot,
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
    # 3-PHASE FORM FILLING: Scan → Map → Fill
    # ------------------------------------------------------------------

    async def _fill_custom_questions(self, page: Page, answers: dict, company: str = "", job_title: str = ""):
        """Intelligent 3-phase form filling.

        Phase 1 – SCAN:  Discover every fillable field, its type, and
                         available dropdown options (for combobox/select).
        Phase 2 – MAP:   Match each field to an answer from the bank (or AI),
                         resolve dropdown choices to actual options, and
                         detect conditional fields that should be skipped.
        Phase 3 – FILL:  Execute the fill plan in order, using the
                         pre-computed answer map.
        """
        # ---------- Phase 1: SCAN ----------
        fields = await self._scan_form_fields(page)
        logger.info(f"Phase 1 SCAN: found {len(fields)} fillable fields")

        # ---------- Phase 2: MAP ----------
        fill_plan = await self._map_answers(fields, answers, company, job_title)
        logger.info(f"Phase 2 MAP: {len(fill_plan)} fields to fill, "
                     f"{len(fields) - len(fill_plan)} skipped")

        # ---------- Phase 3: FILL ----------
        await self._execute_fill_plan(page, fill_plan)

        # ---------- Phase 4: RE-SCAN for dynamic fields ----------
        # Some fields only appear after other fields are filled
        # (e.g. "Please identify your race" after Hispanic/Latino)
        await random_delay(800, 1200)
        new_fields = await self._scan_form_fields(page)
        # Find fields that weren't in the original scan
        known_ids = {f["field_id"] for f in fields}
        dynamic_fields = [f for f in new_fields if f["field_id"] not in known_ids]
        if dynamic_fields:
            logger.info(f"Phase 4 RE-SCAN: found {len(dynamic_fields)} new dynamic fields")
            dynamic_plan = await self._map_answers(dynamic_fields, answers, company, job_title)
            if dynamic_plan:
                logger.info(f"Phase 4 MAP: {len(dynamic_plan)} dynamic fields to fill")
                await self._execute_fill_plan(page, dynamic_plan)

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
        """Build a fill plan: for each field decide the answer + chosen
        option (for dropdowns).  Skip conditional fields when the parent
        didn't trigger them."""
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

            # ── AI fallback for unmatched fields ──
            if best_answer is None:
                try:
                    from services.ai_writer import generate_answer
                    best_answer = await generate_answer(
                        label, company=company, role_title=job_title
                    )
                    from database import get_connection
                    conn = get_connection()
                    conn.execute(
                        "INSERT INTO answer_bank "
                        "(question_pattern, answer, category) VALUES (?, ?, ?)",
                        (text_lower, best_answer, "ai_generated"),
                    )
                    conn.commit()
                    conn.close()
                    answers[text_lower] = best_answer
                    logger.info(f"AI answer saved: '{label[:50]}' -> "
                                f"'{best_answer[:50]}'")
                except Exception as e:
                    logger.warning(f"AI answer failed for '{label[:50]}': {e}")
                    continue

            if not best_answer:
                continue

            # ── Resolve dropdown choice ──
            chosen_option = ""
            if f["options"]:
                chosen_option = self._pick_best_option(
                    f["options"], best_answer
                )
                if chosen_option:
                    logger.info(f"MAP: '{label[:40]}' -> option '{chosen_option}' "
                                f"(answer was '{best_answer[:30]}')")
                else:
                    logger.info(f"MAP: '{label[:40]}' -> no matching option, "
                                f"will type '{best_answer[:30]}'")
            else:
                logger.info(f"MAP: '{label[:40]}' -> '{best_answer[:50]}'")

            plan_entry = {
                **f,
                "answer": best_answer,
                "chosen_option": chosen_option,
            }
            fill_plan.append(plan_entry)
            # Track what we chose so the next field's conditional check works
            prev_chosen = chosen_option if chosen_option else best_answer

        return fill_plan

    def _pick_best_option(self, options: list[str], answer: str) -> str:
        """Pick the best matching option from a list of available choices."""
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

        return best_text

    # ── Phase 3: Fill ────────────────────────────────────────────────

    async def _execute_fill_plan(self, page: Page, plan: list[dict]):
        """Fill every field according to the pre-computed plan."""
        import re as _re
        for entry in plan:
            label = entry["label"]
            fid = entry["field_id"]
            # Use JavaScript getElementById for IDs with special chars like []
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
                        # Use JS for reliability — Greenhouse hides inputs
                        await page.evaluate(
                            """([fid, want]) => {
                                const el = document.getElementById(fid);
                                if (el && el.checked !== want) {
                                    el.checked = want;
                                    el.dispatchEvent(new Event('change', {bubbles: true}));
                                    el.dispatchEvent(new Event('input', {bubbles: true}));
                                    el.dispatchEvent(new Event('click', {bubbles: true}));
                                }
                            }""",
                            [fid, want_checked],
                        )
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
