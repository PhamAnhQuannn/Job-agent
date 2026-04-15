import sqlite3
conn = sqlite3.connect('../data/job_agent.db')
total = conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
print(f'Total jobs in DB: {total}')
print()
rows = conn.execute('SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status ORDER BY cnt DESC').fetchall()
for s, c in rows:
    print(f'  {s:20s}: {c}')
print()
rows2 = conn.execute("SELECT id, company, title, status FROM jobs WHERE status != 'SKIPPED' ORDER BY id DESC").fetchall()
print(f'Non-skipped ({len(rows2)}):')
for i, c, t, s in rows2[:30]:
    print(f'  [{i}] {c:15s} | {t[:45]:45s} | {s}')
if len(rows2) > 30:
    print(f'  ... and {len(rows2)-30} more')
conn.close()
