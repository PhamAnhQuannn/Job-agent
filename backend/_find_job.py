"""Find jobs in the database."""
from database import get_connection
conn = get_connection()

# Check all greenhouse jobs with AUTO_APPLY or SAVED status
print("=== AUTO_APPLY / SAVED greenhouse jobs ===")
rows = conn.execute(
    """SELECT id, company, title, source_url, status FROM jobs 
       WHERE source_url LIKE '%greenhouse%' AND status IN ('AUTO_APPLY', 'SAVED', 'NEW')
       ORDER BY id DESC LIMIT 20"""
).fetchall()
for r in rows:
    print(f"  {r['id']:>6} | {r['status']:12} | {r['company'][:20]:20} | {r['title'][:40]:40} | {r['source_url'][:60]}")

if not rows:
    print("  (none)")
    # Check what statuses exist
    print("\n=== Job status counts (greenhouse) ===")
    rows2 = conn.execute(
        """SELECT status, COUNT(*) as cnt FROM jobs 
           WHERE source_url LIKE '%greenhouse%' 
           GROUP BY status ORDER BY cnt DESC"""
    ).fetchall()
    for r in rows2:
        print(f"  {r['status']:15} {r['cnt']}")

    # Show some recent greenhouse jobs regardless of status
    print("\n=== Recent greenhouse jobs (any status) ===")
    rows3 = conn.execute(
        """SELECT id, company, title, source_url, status FROM jobs 
           WHERE source_url LIKE '%greenhouse%'
           AND title LIKE '%intern%'
           ORDER BY id DESC LIMIT 15"""
    ).fetchall()
    for r in rows3:
        print(f"  {r['id']:>6} | {r['status']:12} | {r['company'][:20]:20} | {r['title'][:40]:40} | {r['source_url'][:60]}")

conn.close()

# Also show all intern jobs regardless of ATS
conn2 = get_connection()
print("\n=== All intern jobs (any source, any status) - last 20 ===")
rows4 = conn2.execute(
    """SELECT id, company, title, source_url, status FROM jobs 
       WHERE title LIKE '%intern%'
       ORDER BY id DESC LIMIT 20"""
).fetchall()
for r in rows4:
    print(f"  {r['id']:>6} | {r['status']:12} | {r['company'][:20]:20} | {r['title'][:40]:40} | {r['source_url'][:60]}")
conn2.close()
