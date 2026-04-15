"""Find non-starburst Greenhouse jobs we can test with."""
from database import get_connection

c = get_connection()

# Reset starburst back
c.execute("UPDATE jobs SET status = 'SKIPPED' WHERE id = 75658")
c.commit()

rows = c.execute("""
    SELECT id, company, title, source_url, status
    FROM jobs
    WHERE source_url LIKE '%greenhouse%'
      AND status = 'SKIPPED'
      AND company NOT IN ('starburst', 'anduril', 'zscaler')
    ORDER BY id DESC
    LIMIT 20
""").fetchall()

print("Available Greenhouse jobs (non-starburst):")
for r in rows:
    print(f"{r[0]:5d}  {r[1]:<25s}  {r[2][:45]:<45s}  {r[3]}")

if not rows:
    print("(none found)")

c.close()
