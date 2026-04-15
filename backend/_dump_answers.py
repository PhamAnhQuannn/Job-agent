"""Dump profile + answer bank to see what's mapped."""
from database import get_connection

conn = get_connection()

print("=== PROFILE ===")
row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
if row:
    for k in row.keys():
        print(f"  {k}: {row[k]}")
else:
    print("  (empty)")

print()
print("=== ANSWER BANK ===")
rows = conn.execute(
    "SELECT id, question_pattern, answer, category FROM answer_bank ORDER BY id"
).fetchall()
print(f"  Total: {len(rows)} entries\n")
for r in rows:
    qp = r["question_pattern"] or ""
    ans = r["answer"] or ""
    cat = r["category"] or ""
    print(f"  [{r['id']:3}] [{cat:15}] {qp[:55]:55} -> {ans[:70]}")

conn.close()
