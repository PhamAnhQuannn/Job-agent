from database import get_connection
c = get_connection()
rows = c.execute(
    "SELECT question_pattern, answer FROM answer_bank "
    "WHERE question_pattern LIKE '%graduat%' OR question_pattern LIKE '%expect%' "
    "OR question_pattern LIKE '%enrolled%' OR question_pattern LIKE '%university%' "
    "OR question_pattern LIKE '%completion%' OR question_pattern LIKE '%program%'"
).fetchall()
for r in rows:
    print(f"{r[0][:70]:<70s}  {r[1][:50]}")
c.close()
