import sys
from database import get_connection

conn = get_connection()

# If "reset" arg passed, reset APPLY_FAILED jobs back to AUTO_APPLY
if len(sys.argv) > 1 and sys.argv[1] == "reset":
    n = conn.execute(
        "UPDATE jobs SET status='AUTO_APPLY', failure_step=NULL WHERE status='APPLY_FAILED'"
    ).rowcount
    conn.commit()
    print(f"Reset {n} APPLY_FAILED jobs back to AUTO_APPLY")

rows = conn.execute(
    "SELECT id, company, title, status, failure_step FROM jobs "
    "WHERE status IN ('SUBMITTED','APPLY_FAILED','AUTO_APPLY','REVIEW') "
    "ORDER BY status, id"
).fetchall()

for r in rows:
    print(f"  [{r['status']}] id={r['id']} {r['company']} | {r['title']} | fail={r['failure_step']}")

print(f"\nTotal: {len(rows)}")
conn.close()
