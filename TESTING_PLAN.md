# Job Auto-Apply Agent — Testing Plan

## Testing Strategy
- Unit tests for each module in isolation
- Integration tests for connected flows
- Dry run mode for apply bot (NEVER submit in test)
- End-to-end test after all phases complete

---

## Phase 1: Project Setup

| Step | What to Test | How | Pass Criteria |
|---|---|---|---|
| 1.2 | FastAPI starts | `curl http://localhost:8000/health` | Returns 200 |
| 1.3 | Next.js starts | Open `http://localhost:3000` | Page loads |
| 1.4 | SQLite tables | Query `sqlite_master` for all 7 tables | All exist with correct columns |
| 1.5 | Profile seeded | `GET /api/profile` | Returns your fixed info |

---

## Phase 2: Core Backend APIs

| Step | What to Test | How | Pass Criteria |
|---|---|---|---|
| 2.1 | Profile read | `GET /api/profile` | Returns all fields |
| 2.1 | Profile update | `PUT /api/profile` with changed phone | Phone persists after restart |
| 2.2 | Answer bank CRUD | POST → GET → PUT → DELETE | Each operation works, delete removes row |
| 2.3 | Resume upload | POST PDF file | File exists in `data/resumes/`, path saved in DB |
| 2.4 | Filter engine | Pass 10 test job descriptions | Correct apply/review/skip for each |
| 2.5 | Jobs list | Seed 5 jobs, filter by status | Correct count per status |

### Filter Engine Test Cases

```
Case 1: "Software Engineer Intern, Java, Python, SQL, backend"
  Expected: score ≥ 5 → AUTO APPLY

Case 2: "Mechanical Engineer, CAD, SolidWorks, AutoCAD"
  Expected: hard skip → SKIP

Case 3: "Software Engineer, U.S. citizen required"
  Expected: hard skip → SKIP

Case 4: "Data Analyst Intern, Python, Excel, SQL"
  Expected: score 2-4 → REVIEW

Case 5: "Robotics Engineer, embedded systems, C++"
  Expected: negative keywords → SKIP

Case 6: "Full Stack Intern, React, Node.js, JavaScript"
  Expected: score ≥ 5 → AUTO APPLY

Case 7: "Software Engineer Intern" (no description body)
  Expected: title match only, score 2-4 → REVIEW

Case 8: "Backend Developer, Java, Spring Boot, REST APIs, cloud"
  Expected: score ≥ 5 → AUTO APPLY

Case 9: "java" must NOT match "javascript"
  Expected: word boundary regex works

Case 10: Duplicate job (same company + title + location hash)
  Expected: rejected as DUPLICATE
```

---

## Phase 3: Dashboard

| Step | What to Test | How | Pass Criteria |
|---|---|---|---|
| 3.1 | Profile page | Open → check fields → edit → refresh | Edit persists |
| 3.2 | Answer bank page | Add → edit → delete from UI | All operations reflect |
| 3.3 | Jobs list | Seed mixed-status jobs, use status filter | Filter shows correct subset |
| 3.4 | Review queue | Seed 3 REVIEW_NEEDED + 5 SUBMITTED | Queue shows exactly 3 |
| 3.5 | Job detail | Click job → view full info | Description, score, screenshot all render |
| 3.6 | Stats page | Seed 10 jobs with mixed statuses | Counts match DB reality |

---

## Phase 4: Job Scanner

| Step | What to Test | How | Pass Criteria |
|---|---|---|---|
| 4.1 | Greenhouse scraper | Run on known public board | Returns ≥ 1 job with title, company, URL |
| 4.2 | Lever scraper | Run on known public board | Returns ≥ 1 job |
| 4.3 | Deduplication | Insert same job twice | Second insert → status = DUPLICATE |
| 4.4 | Scheduler | Start scheduler, wait 2 cycles | New jobs appear in DB |
| 4.5 | Multi-source | Run 2 scrapers | Jobs from both sources in same table |

### Scanner edge cases
```
- Job listing with no description → still saves, goes to REVIEW
- Job listing with Unicode characters → saves correctly
- Board with 0 jobs → no crash, log "no jobs found"
- Network timeout → retry once, then log error
- Already-seen URL → skip without crash
```

---

## Phase 5: AI Writer

| Step | What to Test | How | Pass Criteria |
|---|---|---|---|
| 5.1 | LLM connection | Send test prompt | Non-empty response, no error |
| 5.2 | Cover letter | Generate for "Google SWE Intern" | Contains "Google", mentions your skills |
| 5.2 | Cover letter length | Check word count | 150-300 words (not too short/long) |
| 5.3 | Custom answer | "Why this role?" | Relevant, non-generic answer |
| 5.4 | PDF export | Save cover letter as PDF | Opens in PDF reader without error |

### AI quality checks
```
- No hallucinated experience (doesn't invent jobs/skills you don't have)
- No placeholder text ("[Your Name]", "{company}")
- Company name spelled correctly
- Role title matches job posting
- Does not repeat same letter for different companies
```

---

## Phase 6: Email Manager

| Step | What to Test | How | Pass Criteria |
|---|---|---|---|
| 6.1 | Email generator | Generate 3 emails for different jobs | All unique, match format `apply-*@domain` |
| 6.1 | No collision | Generate 100 emails | All unique |
| 6.2 | IMAP reader | Send test email to catch-all | Reader picks it up within 5 min |
| 6.3 | Verification extractor | Mock verification email | Extracts code or link correctly |
| 6.4 | Job matching | Email to `apply-google-swe@domain` | Linked to correct job in DB |
| 6.5 | OA detection | Mock HackerRank invite email | Assessment row created with link + deadline |

### Email edge cases
```
- Email with no body → logged but no crash
- Email to unknown address → logged as unmatched
- Multiple emails for same job → all linked correctly
- HTML-only email → body parsed correctly
- Attachment in email → logged (not processed)
```

---

## Phase 7: Apply Bot

| Step | What to Test | How | Pass Criteria |
|---|---|---|---|
| 7.1 | Playwright launch | Open google.com | Page title correct |
| 7.2 | ATS detector | 3 test URLs | Correct adapter returned per URL |
| 7.3 | Greenhouse dry run | Fill real Greenhouse form, DON'T submit | All fields filled, screenshot saved |
| 7.4 | Lever dry run | Fill real Lever form, DON'T submit | All fields filled, screenshot saved |
| 7.6 | Screenshot | After form fill | File exists in `data/screenshots/`, valid PNG |
| 7.7 | Error recovery | Kill browser mid-fill | Restarts from failed step, not from scratch |
| 7.8 | Staggered timing | Queue 5 jobs | 30-90s random gap between each |

### DRY RUN PROTOCOL (CRITICAL)
```
Config: DRY_RUN=true (default)

When DRY_RUN=true:
  ✓ Opens page
  ✓ Logs in / creates account
  ✓ Fills all form fields
  ✓ Uploads resume + cover letter
  ✓ Takes screenshot
  ✗ Does NOT click submit
  → Logs: "DRY RUN — would have submitted application to {company}"
  → Status: DRAFTED (not SUBMITTED)

Switch to DRY_RUN=false ONLY after:
  - 10+ successful dry runs on Greenhouse
  - 10+ successful dry runs on Lever
  - All fields verified correct in screenshots
  - No errors in logs
```

### Apply bot edge cases
```
- Form has unexpected required field → pause, send to REVIEW
- CAPTCHA detected → pause, send to REVIEW
- Login page changed layout → log error, send to REVIEW
- File upload rejects PDF → log error, try different upload method
- Session expired mid-form → re-login, retry from last step
- Site is down / 500 error → mark FAILED, log, move to next job
```

---

## Phase 8: Tracking + Export

| Step | What to Test | How | Pass Criteria |
|---|---|---|---|
| 8.1 | Status update | SUBMITTED → REJECTED via API | DB reflects change |
| 8.2 | Daily stats | Seed 20 jobs, run aggregation | All counts correct |
| 8.3 | Excel export | Export → open file | 5 sheets, row counts match DB |
| 8.3 | Excel re-export | Change data → re-export | Excel reflects changes |
| 8.4 | Daily summary | View summary on dashboard | Numbers match raw DB |
| 8.5 | Credential encryption | Encrypt → store → decrypt | Decrypted value matches original |
| 8.5 | No plaintext | Read DB file with text editor | No readable passwords |

---

## End-to-End Test

```
Full pipeline test (DRY RUN):

  1. Scanner finds a real job on Greenhouse         → job in DB, status=FOUND
  2. Dedup confirms it's new                        → not DUPLICATE
  3. Filter scores ≥ 5                              → status=MATCHED
  4. Email generated: apply-company-date@domain     → unique, stored in DB
  5. Cover letter generated via AI                  → file saved, no hallucinations
  6. Answer bank matches all known questions         → all answers filled
  7. Playwright opens page (DRY RUN=true)           → browser opens
  8. Fills all fields correctly                     → screenshot verifies
  9. Uploads resume + cover letter                  → files attached
  10. Screenshot taken                              → exists in data/screenshots/
  11. Status = DRAFTED (dry run stops here)         → NOT submitted
  12. Excel export includes this job                → row visible in spreadsheet
  13. Dashboard shows it in jobs list               → correct status + details

Pass: every step has correct data, no errors in logs.
```

---

## How to Run Tests

```bash
# Backend unit tests
cd backend
pytest tests/ -v

# Filter engine tests specifically
pytest tests/test_filter_engine.py -v

# Frontend (if applicable)
cd frontend
npm test

# Apply bot dry run (manual verification)
cd backend
python -m automation.apply_bot --dry-run --job-id 1

# Full pipeline dry run
python -m scripts.test_pipeline --dry-run
```
