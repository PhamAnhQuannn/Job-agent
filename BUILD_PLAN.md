# Job Auto-Apply Agent — Build Plan

## Overview
Single-user personal auto job apply agent. Local web app.
Goal: maximize application volume with rule-based filtering + AI cover letters + browser automation.

## Tech Stack
- Frontend: Next.js
- Backend: FastAPI (Python)
- Automation: Playwright
- Database: SQLite → auto-export to Excel
- AI: LLM API (TBD)
- Email: Custom domain catch-all

## Workflow
```
SCAN → DEDUP → FILTER → PREPARE → APPLY → TRACK → MONITOR
```

---

## Phase 1: Project Setup
- [ ] 1.1 Scaffold folder structure (backend, frontend, automation, data)
- [ ] 1.2 Initialize FastAPI backend with dependencies
- [ ] 1.3 Initialize Next.js frontend
- [ ] 1.4 Set up SQLite database with all tables
- [ ] 1.5 Seed fixed profile into DB

## Phase 2: Core Backend APIs
- [ ] 2.1 Profile API — read/update personal info
- [ ] 2.2 Answer bank API — CRUD for reusable Q&A pairs
- [ ] 2.3 Resume upload + file storage
- [ ] 2.4 Job filter engine — keyword scoring logic (positive/negative/hard-skip)
- [ ] 2.5 Jobs API — list, filter by status, update status

## Phase 3: Dashboard (Frontend)
- [ ] 3.1 Profile page — view/edit fixed info
- [ ] 3.2 Answer bank page — manage Q&A pairs
- [ ] 3.3 Jobs list page — all jobs, filter by status
- [ ] 3.4 Review queue page — jobs needing manual decision
- [ ] 3.5 Job detail page — description, score, status, screenshot
- [ ] 3.6 Daily summary / stats page

## Phase 4: Job Scanner
- [ ] 4.1 Greenhouse board scraper
- [ ] 4.2 Lever board scraper
- [ ] 4.3 Deduplication logic (hash: company + title + location)
- [ ] 4.4 Scanner scheduler (runs every 15-60 min)
- [ ] 4.5 Additional sources (Indeed, Adzuna API, Handshake)

## Phase 5: AI Writer
- [ ] 5.1 LLM API integration (provider TBD)
- [ ] 5.2 Cover letter generation (company + role + skills → letter)
- [ ] 5.3 Custom answer generation for unmatched questions
- [ ] 5.4 Cover letter PDF export

## Phase 6: Email Manager
- [ ] 6.1 Email address generator (per-job unique: apply-{company}-{date}@domain)
- [ ] 6.2 IMAP inbox reader (poll every 5 min)
- [ ] 6.3 Verification code extractor (auto-verify accounts)
- [ ] 6.4 Email-to-job matching (link reply → application)
- [ ] 6.5 OA detection (HackerRank, CodeSignal links)
- [ ] 6.6 Dashboard inbox view

## Phase 7: Apply Bot (Playwright)
- [ ] 7.1 Playwright setup + stealth config (random delays, human-like)
- [ ] 7.2 ATS platform detector (URL → adapter)
- [ ] 7.3 Greenhouse adapter — login, fill, upload, submit
- [ ] 7.4 Lever adapter — login, fill, upload, submit
- [ ] 7.5 Workday adapter (later)
- [ ] 7.6 Screenshot capture on submit/failure
- [ ] 7.7 Error recovery — retry from failed step
- [ ] 7.8 Apply scheduler — staggered 30-90s delays, daily batches

## Phase 8: Tracking + Export
- [ ] 8.1 Status update API (SUBMITTED → REJECTED / INTERVIEW / OFFER)
- [ ] 8.2 Daily stats aggregation
- [ ] 8.3 SQLite → Excel auto-export (all sheets)
- [ ] 8.4 Daily summary report
- [ ] 8.5 Credential storage with encryption

---

## Folder Structure (Target)
```
job-agent/
├── backend/
│   ├── main.py                 # FastAPI app entry
│   ├── database.py             # SQLite connection + table creation
│   ├── models.py               # Pydantic models
│   ├── routers/
│   │   ├── profile.py          # Profile API
│   │   ├── jobs.py             # Jobs API
│   │   ├── answers.py          # Answer bank API
│   │   ├── resume.py           # Resume upload API
│   │   └── export.py           # Excel export API
│   ├── services/
│   │   ├── filter_engine.py    # Keyword scoring
│   │   ├── ai_writer.py        # Cover letter generation
│   │   ├── email_manager.py    # Email generation + IMAP
│   │   └── exporter.py         # SQLite → Excel sync
│   ├── scanner/
│   │   ├── greenhouse.py       # Greenhouse scraper
│   │   ├── lever.py            # Lever scraper
│   │   └── scheduler.py        # Scan scheduler
│   ├── automation/
│   │   ├── apply_bot.py        # Main apply orchestrator
│   │   ├── adapters/
│   │   │   ├── greenhouse.py   # Greenhouse form filler
│   │   │   ├── lever.py        # Lever form filler
│   │   │   └── workday.py      # Workday form filler
│   │   └── stealth.py          # Anti-detection config
│   └── requirements.txt
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            # Dashboard home
│   │   │   ├── profile/page.tsx    # Profile page
│   │   │   ├── jobs/page.tsx       # Jobs list
│   │   │   ├── review/page.tsx     # Review queue
│   │   │   ├── answers/page.tsx    # Answer bank
│   │   │   ├── inbox/page.tsx      # Email inbox
│   │   │   └── export/page.tsx     # Reports + export
│   │   └── components/
│   └── next.config.js
├── data/
│   ├── job_agent.db                # SQLite database
│   ├── jobs_tracker.xlsx           # Auto-exported Excel
│   ├── resumes/                    # Uploaded resume files
│   ├── cover_letters/              # Generated cover letters
│   └── screenshots/                # Submit/failure screenshots
├── BUILD_PLAN.md                   # This file
└── .env                            # API keys, email credentials
```

---

## DB Tables
- `profile` — 1 row, fixed personal info
- `jobs` — all jobs found, with score + status
- `credentials` — encrypted login info per platform
- `answer_bank` — reusable Q&A pairs
- `assessments` — OA tracking (links, deadlines)
- `emails` — inbox log, matched to jobs
- `daily_stats` — daily aggregation

## Job Statuses
```
FOUND → DUPLICATE (end)
FOUND → SKIPPED (end)
FOUND → MATCHED → DRAFTED → APPLYING → SUBMITTED
FOUND → MATCHED → REVIEW_NEEDED → DRAFTED → APPLYING → SUBMITTED
APPLYING → FAILED (retryable)
SUBMITTED → REJECTED (end)
SUBMITTED → INTERVIEW → OFFER
any → WITHDRAWN (end)
```

## Pending Decisions
- [ ] Custom email domain name
- [ ] LLM API provider (OpenAI / Claude / Gemini)
- [ ] First job source to implement
- [ ] User profile data to seed
