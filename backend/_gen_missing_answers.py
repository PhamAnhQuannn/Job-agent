"""For scanned fields with no answer bank match:
- Required questions (marked with *): use AI to generate an answer
- Non-required questions: leave empty (skip)
Uses existing answer bank as context for AI."""
import asyncio
import json
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from database import get_connection
from services.ai_writer import generate_answer

SCAN_PATH = os.path.join(os.path.dirname(__file__), "data", "screenshots", "last_scan.json")


def load_scan():
    with open(SCAN_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_answers():
    conn = get_connection()
    rows = conn.execute("SELECT question_pattern, answer, category FROM answer_bank").fetchall()
    conn.close()
    return {r["question_pattern"]: r["answer"] for r in rows}


def find_best_match(label_lower, answers):
    best_answer, best_len = None, 0
    for pattern, answer in answers.items():
        if pattern.lower() in label_lower and len(pattern) > best_len:
            best_answer = answer
            best_len = len(pattern)
    return best_answer


def get_relevant_context(answers):
    """Pull key answers from the bank to give AI full context."""
    context_keys = [
        "first name", "last name", "email", "phone", "github",
        "linkedin", "website", "school", "degree", "graduation",
        "gpa", "work authorization", "require sponsorship",
        "willing to relocate", "years of experience",
        "programming languages", "current location",
        "start date", "internship duration",
    ]
    lines = []
    for key in context_keys:
        for pattern, answer in answers.items():
            if key in pattern.lower() and answer:
                lines.append(f"  {pattern}: {answer}")
                break
    return "\n".join(lines)


async def main():
    fields = load_scan()
    answers = get_answers()

    # Find unmatched fields — separate required vs optional
    unmatched_required = []
    unmatched_optional = []
    for f in fields:
        label = f["label"]
        text_lower = label.lower()
        if f.get("is_conditional"):
            continue
        match = find_best_match(text_lower, answers)
        if not match:
            is_required = label.rstrip().endswith("*")
            if is_required:
                unmatched_required.append(f)
            else:
                unmatched_optional.append(f)

    if unmatched_optional:
        print(f"Skipping {len(unmatched_optional)} non-required fields (no * marker):")
        for f in unmatched_optional:
            print(f"  SKIP  '{f['label'][:60]}'")
        print()

    if not unmatched_required:
        print("All required (*) fields already have answers!")
        return

    print(f"Found {len(unmatched_required)} required fields needing AI answers:\n")

    # Build context from existing bank
    bank_context = get_relevant_context(answers)

    conn = get_connection()
    for f in unmatched_required:
        label = f["label"]
        options = f.get("options", [])

        print(f"--- Question: '{label}'")
        if options:
            print(f"    Options: {options}")

        # Build a richer prompt that includes the dropdown options
        question_for_ai = label
        if options:
            question_for_ai += f"\n\nAvailable options (pick one exactly): {options}"
            question_for_ai += "\n\nIMPORTANT: Your answer must be EXACTLY one of the available options listed above, word-for-word."

        question_for_ai += f"\n\nExisting applicant info:\n{bank_context}"

        answer = await generate_answer(
            question=question_for_ai,
            company="Anduril Industries",
            role_title="Software Engineer Intern",
        )
        print(f"    AI Answer: {answer[:100]}")

        # For dropdown questions, try to match to an exact option
        if options:
            answer_lower = answer.lower().strip()
            # Check if the AI answer exactly matches an option
            exact = None
            for opt in options:
                if opt.lower() in answer_lower or answer_lower in opt.lower():
                    exact = opt
                    break
            if exact:
                print(f"    Matched option: '{exact}'")
                answer = exact

        # Save to answer bank with a normalized pattern
        pattern = label.lower().strip().rstrip("*").strip()
        # Check if this pattern already exists
        existing = conn.execute(
            "SELECT id FROM answer_bank WHERE question_pattern = ?", (pattern,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE answer_bank SET answer = ? WHERE id = ?",
                (answer, existing["id"]),
            )
            print(f"    Updated existing entry #{existing['id']}")
        else:
            conn.execute(
                "INSERT INTO answer_bank (question_pattern, answer, category) VALUES (?, ?, ?)",
                (pattern, answer, "ai_generated"),
            )
            print(f"    Saved new answer to bank")
        conn.commit()
        print()

    conn.close()

    # Re-run mapping to verify
    print("=" * 70)
    print("RE-CHECKING MAPPING...")
    print("=" * 70)
    answers = get_answers()  # reload
    matched = 0
    total = 0
    for f in fields:
        label = f["label"]
        if f.get("is_conditional"):
            continue
        total += 1
        match = find_best_match(label.lower(), answers)
        status = "OK" if match else "MISS"
        if match:
            matched += 1
        print(f"  {status:4} '{label[:60]}'" + (f" -> '{match[:50]}'" if match else ""))

    print(f"\n  Result: {matched}/{total} matched")


asyncio.run(main())
