from database import get_connection
conn = get_connection()

rows = conn.execute("SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status ORDER BY cnt DESC").fetchall()
print("=== Jobs by Status ===")
for r in rows:
    print(f"  {r['status']}: {r['cnt']}")

print("\n=== Top AUTO_APPLY Jobs ===")
top = conn.execute(
    "SELECT company, title, location, score FROM jobs WHERE status = 'AUTO_APPLY' ORDER BY score DESC LIMIT 15"
).fetchall()
for j in top:
    print(f"  [{j['score']}] {j['company']} - {j['title']} ({j['location']})")

print("\n=== Sample REVIEW_NEEDED ===")
rev = conn.execute(
    "SELECT company, title, score FROM jobs WHERE status = 'REVIEW_NEEDED' ORDER BY score DESC LIMIT 10"
).fetchall()
for j in rev:
    print(f"  [{j['score']}] {j['company']} - {j['title']}")

print("\n=== Companies Found ===")
comps = conn.execute(
    "SELECT company, COUNT(*) as cnt FROM jobs GROUP BY company ORDER BY cnt DESC"
).fetchall()
for c in comps:
    print(f"  {c['company']}: {c['cnt']} jobs")

conn.close()
