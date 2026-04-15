from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
import sqlite3
import os
from database import get_db
from services.exporter import export_to_excel, aggregate_daily_stats

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/stats")
def get_daily_stats(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM daily_stats ORDER BY date DESC LIMIT 30"
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/excel")
def generate_excel():
    """Export all data to Excel and return the file."""
    filepath = export_to_excel()
    filename = os.path.basename(filepath)
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@router.post("/aggregate")
def trigger_aggregate():
    """Manually trigger daily stats aggregation."""
    aggregate_daily_stats()
    return {"status": "aggregated"}
