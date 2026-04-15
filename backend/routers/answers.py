from fastapi import APIRouter, Depends, HTTPException
import sqlite3
from database import get_db
from models import AnswerBase, AnswerResponse

router = APIRouter(prefix="/api/answers", tags=["answers"])


@router.get("", response_model=list[AnswerResponse])
def list_answers(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM answer_bank ORDER BY category, id").fetchall()
    return [dict(r) for r in rows]


@router.post("", response_model=AnswerResponse)
def create_answer(answer: AnswerBase, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.execute(
        "INSERT INTO answer_bank (question_pattern, answer, category) VALUES (?, ?, ?)",
        (answer.question_pattern, answer.answer, answer.category),
    )
    db.commit()
    return {"id": cursor.lastrowid, **answer.model_dump()}


@router.put("/{answer_id}", response_model=AnswerResponse)
def update_answer(
    answer_id: int,
    answer: AnswerBase,
    db: sqlite3.Connection = Depends(get_db),
):
    db.execute(
        "UPDATE answer_bank SET question_pattern = ?, answer = ?, category = ? WHERE id = ?",
        (answer.question_pattern, answer.answer, answer.category, answer_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM answer_bank WHERE id = ?", (answer_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Answer not found")
    return dict(row)


@router.delete("/{answer_id}")
def delete_answer(answer_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM answer_bank WHERE id = ?", (answer_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Answer not found")
    db.execute("DELETE FROM answer_bank WHERE id = ?", (answer_id,))
    db.commit()
    return {"deleted": True}
