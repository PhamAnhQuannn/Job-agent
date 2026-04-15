"""Fix answer bank entries that produce wrong matches for common questions."""
from database import get_connection

conn = get_connection()

# --- Fix: old AI-generated answer for "how did you learn" patterns ---
# Find and update any pattern containing "how did you learn" that has a long AI answer
rows = conn.execute(
    "SELECT id, question_pattern, answer FROM answer_bank WHERE question_pattern LIKE '%how did you learn%'"
).fetchall()

for r in rows:
    if r["answer"] != "Linkedin":
        conn.execute("UPDATE answer_bank SET answer = ? WHERE id = ?", ("Linkedin", r["id"]))
        print(f"  UPDATED [{r['id']}] '{r['question_pattern']}' -> 'Linkedin'  (was: '{r['answer'][:60]}...')")
    else:
        print(f"  OK      '{r['question_pattern']}' already 'Linkedin'")

conn.commit()
conn.close()
print("\nDone.")
