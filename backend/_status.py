from database import get_connection

conn = get_connection()
print("=== Job statuses ===")
for r in conn.execute(
    "SELECT id, company, title, status, failure_step, screenshot_path FROM jobs "
    "WHERE status IN ('SUBMITTED','APPLY_FAILED','AUTO_APPLY') ORDER BY score DESC"
).fetchall():
    d = dict(r)
    print(f"  [{d['status']}] {d['company']} | {d['title']}")
    if d.get("failure_step"):
        print(f"    fail: {d['failure_step']}")
    if d.get("screenshot_path"):
        print(f"    screenshot: {d['screenshot_path']}")
conn.close()
