# Mac Device Support — Implementation Requirements

This document tracks the work needed to make **job-agent** run natively on macOS (Apple Silicon M-series and Intel x86_64).

---

## Current State

The project was developed and tested exclusively on **Windows 11 (x64)**.  
Several areas contain Windows-specific assumptions that must be addressed before the agent can run reliably on macOS.

---

## Required Changes

### 1. User-Agent String — `browser.py`

**File:** `backend/automation/browser.py` — line ~44

The Chromium context is launched with a hardcoded Windows user-agent:

```python
user_agent=(
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
),
```

**Required work:**
- Detect the host OS at startup (`sys.platform == "darwin"` / `platform.machine() == "arm64"`).
- Substitute a macOS Chrome user-agent:
  - Intel: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ...`
  - Apple Silicon: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ...` *(Chrome still reports Intel on ARM via Rosetta layer — verify current Chrome 120+ behaviour)*
- Alternatively, expose a `USER_AGENT` environment variable so it can be overridden without code changes.

---

### 2. Virtual Environment Setup — Developer Docs / Scripts

All documented commands use Windows paths and PowerShell syntax:

```powershell
# Windows
python -m venv .venv
.\.venv\Scripts\activate
```

**Required work:**
- Document the macOS equivalent in `README.md` / `CONTRIBUTING.md`:
  ```bash
  # macOS / Linux
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- Update any helper scripts (`.ps1`, batch files) with macOS `bash`/`zsh` equivalents or replace with cross-platform scripts.

---

### 3. Playwright Browser Installation

Playwright on macOS requires the same `playwright install` step, but the Chromium binary lives under `~/Library/Caches/ms-playwright/` instead of `%LOCALAPPDATA%\ms-playwright\`.

**Required work:**
- Confirm `playwright install chromium` works on both Intel and Apple Silicon (Rosetta 2 is usually transparent).
- Add a one-line install note to the setup docs.
- On Apple Silicon, verify that `--no-sandbox` (currently passed in `create_browser()`) is still needed or can be removed for macOS.

---

### 4. asyncio Event Loop Policy

Python on Windows uses `ProactorEventLoop` by default (needed for `asyncio.subprocess` on Windows). On macOS the default loop is fine, but mixing Playwright's `async_playwright` with `asyncio.run()` may surface different edge cases.

**Required work:**
- Check whether `asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())` is set anywhere explicitly — remove/guard it behind `if sys.platform == "win32"`.
- Run the full test suite on macOS and fix any event-loop–related errors.

---

### 5. File Path Separators

The codebase uses `os.path.join()` throughout (good), but a few debug scripts use hardcoded Windows-style paths:

```python
# Example from _test_fill.py env setup
os.environ['PYTHONPATH'] = 'd:\\job-agent\\backend'
```

**Required work:**
- Audit all `backend/_*.py` helper/test scripts for hardcoded `d:\...` paths.
- Replace with `pathlib.Path(__file__).parent.resolve()` or equivalent relative paths.

---

### 6. Environment Variables & `.env` File

The project reads credentials from the environment (or a `.env` file via `python-dotenv`).  
The `.env` format is the same on both OSes, but the way environment variables are set differs in documentation/scripts.

**Required work:**
- Ensure a `sample.env` / `.env.example` file exists with all required keys documented. *(No file found yet.)*
- Document macOS export syntax:
  ```bash
  export OPENAI_API_KEY=sk-...
  export GMAIL_ADDRESS=...
  export GMAIL_APP_PASSWORD=...
  ```

---

### 7. SQLite Database Path

The SQLite DB path resolves relative to the module file, which should be OS-agnostic, but confirm the `get_connection()` call in `database.py` uses `pathlib` or `os.path` (not a raw string).

**Required work:**
- Verify `database.py` — confirm `DB_PATH` resolution is cross-platform.
- Add a smoke-test that the DB can be created and read on macOS.

---

### 8. PDF Resume Export — `pdf_export.py`

`services/pdf_export.py` uses `fpdf2`. This library is pure Python and cross-platform, but font paths or system font lookups may differ on macOS.

**Required work:**
- Test PDF generation on macOS.
- If any system font is referenced, replace with a bundled font or a macOS-compatible fallback.

---

### 9. CI / GitHub Actions

Currently there is no CI pipeline.

**Required work:**
- Add a GitHub Actions workflow (`.github/workflows/test.yml`) that runs the test suite on:
  - `ubuntu-latest` (proxy for macOS compatibility in most cases)
  - `macos-latest` (for true macOS validation)
- Matrix example:
  ```yaml
  strategy:
    matrix:
      os: [ubuntu-latest, macos-latest, windows-latest]
  ```

---

## Testing Checklist (macOS)

| # | Area | Status |
|---|------|--------|
| 1 | `python3 -m venv .venv && source .venv/bin/activate` | ☐ |
| 2 | `pip install -r requirements.txt` | ☐ |
| 3 | `playwright install chromium` | ☐ |
| 4 | Backend starts: `uvicorn main:app --reload` | ☐ |
| 5 | Frontend starts: `npm run dev` | ☐ |
| 6 | `_test_fill.py` DRY_RUN=true on a Greenhouse URL | ☐ |
| 7 | `_test_fill.py` DRY_RUN=false (full submit) | ☐ |
| 8 | Email polling (`capture_confirmation_email`) | ☐ |
| 9 | PDF export | ☐ |
| 10 | Full unit test suite: `pytest tests/` | ☐ |

---

## Notes

- Minimum Python version: **3.11+** (3.14 used on Windows dev machine; verify compatibility on macOS Python 3.11/3.12).
- Node.js **18+** required for the Next.js frontend (same on all OSes).
- Apple Silicon users may need `arch -x86_64` for some Playwright builds — verify before releasing.
