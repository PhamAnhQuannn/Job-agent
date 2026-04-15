from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import profile, jobs, answers, resume, export, scanner, ai, emails, apply
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scanner.scheduler import run_scan
from automation.apply_bot import run_full_queue, scan_and_apply
from services.email_manager import process_emails
from services.exporter import aggregate_daily_stats
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

app = FastAPI(title="Job Auto-Apply Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(answers.router)
app.include_router(resume.router)
app.include_router(export.router)
app.include_router(scanner.router)
app.include_router(ai.router)
app.include_router(emails.router)
app.include_router(apply.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup():
    init_db()

    # Schedule recurring jobs
    # Scan + apply cycle every 30 minutes
    scheduler.add_job(scan_and_apply, "interval", minutes=30, id="scan_and_apply")
    scheduler.add_job(process_emails, "interval", minutes=5, id="email_poller")
    scheduler.add_job(aggregate_daily_stats, "cron", hour=23, minute=55, id="daily_stats")
    scheduler.start()
    logger.info("Schedulers started: scan+apply (30min), email (5min), daily stats (23:55)")

    # Run initial scan + apply on startup (non-blocking)
    async def _initial_run():
        await asyncio.sleep(5)  # Let the server finish starting
        logger.info("Running initial scan & apply cycle...")
        try:
            result = await scan_and_apply()
            logger.info(f"Initial cycle complete: {result}")
        except Exception as e:
            logger.error(f"Initial scan & apply failed: {e}")

    loop = asyncio.get_event_loop()
    loop.create_task(_initial_run())


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown(wait=False)
