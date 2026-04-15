from fastapi import APIRouter
from scanner.scheduler import run_scan, GREENHOUSE_BOARDS, LEVER_BOARDS

router = APIRouter(prefix="/api/scanner", tags=["scanner"])


@router.post("/run")
async def trigger_scan():
    """Manually trigger a scan cycle."""
    summary = await run_scan()
    return {"message": "Scan complete", "summary": summary}


@router.get("/config")
def get_scanner_config():
    """Return current scanner board configuration."""
    return {
        "greenhouse_boards": GREENHOUSE_BOARDS,
        "lever_boards": LEVER_BOARDS,
    }
