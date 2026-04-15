"""Offline Phase 2 test: load the saved scan JSON from last_scan.json,
run the answer bank matching logic locally (no browser), and show
exactly what would be matched, what option picked, and what's missing."""
import json
import os
import re
from database import get_connection


def load_scan():
    path = os.path.join(os.path.dirname(__file__), "data", "screenshots", "last_scan.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_answers():
    conn = get_connection()
    rows = conn.execute("SELECT question_pattern, answer FROM answer_bank").fetchall()
    conn.close()
    return {r["question_pattern"]: r["answer"] for r in rows}


def get_profile():
    conn = get_connection()
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {}
    d = dict(row)
    parts = (d.get("full_name") or "").split(" ", 1)
    d["first_name"] = parts[0] if parts else ""
    d["last_name"] = parts[1] if len(parts) > 1 else ""
    return d


def pick_best_option(options, answer):
    answer_lower = answer.lower().strip()
    yes_no = None
    if answer_lower.startswith("yes"):
        yes_no = "yes"
    elif answer_lower.startswith("no"):
        yes_no = "no"

    best_text, best_score = "", 0
    for opt in options:
        opt_lower = opt.lower().strip()
        if opt_lower == answer_lower:
            return opt
        if yes_no and opt_lower.startswith(yes_no):
            score = 50 + len(opt_lower)
            if score > best_score:
                best_text, best_score = opt, score
            continue
        if answer_lower in opt_lower:
            score = len(answer_lower)
            if score > best_score:
                best_text, best_score = opt, score
        elif opt_lower in answer_lower:
            score = len(opt_lower)
            if score > best_score:
                best_text, best_score = opt, score
    return best_text


def main():
    fields = load_scan()
    answers = get_answers()
    profile = get_profile()

    # Build the full answer map (same as GreenhouseAdapter._build_answer_map concept)
    # Profile basics are handled separately by the adapter, so focus on custom questions
    # But we include them for completeness
    full_answers = {}
    mapping = {
        "first name": profile.get("first_name", ""),
        "last name": profile.get("last_name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "linkedin": profile.get("linkedin", ""),
        "website": profile.get("github", ""),
        "github": profile.get("github", ""),
    }
    for k, v in mapping.items():
        if v:
            full_answers[k] = v
    for k, v in answers.items():
        full_answers[k.lower()] = v

    print(f"{'='*90}")
    print(f"PHASE 2 — ANSWER MAPPING (offline, {len(fields)} fields)")
    print(f"{'='*90}\n")

    matched = 0
    unmatched = 0
    skipped = 0

    for i, f in enumerate(fields, 1):
        label = f["label"]
        text_lower = label.lower()
        options = f.get("options", [])
        is_cond = f.get("is_conditional", False)

        # Find best answer (longest match)
        best_answer = None
        best_pattern = None
        best_len = 0
        for pattern, answer in full_answers.items():
            if pattern in text_lower and len(pattern) > best_len:
                best_answer = answer
                best_pattern = pattern
                best_len = len(pattern)

        # Resolve dropdown
        chosen_option = ""
        if best_answer and options:
            chosen_option = pick_best_option(options, best_answer)

        # Print
        status = ""
        if is_cond:
            status = "COND"
        elif best_answer:
            status = "OK"
            matched += 1
        else:
            status = "MISS"
            unmatched += 1

        print(f"  [{i:2d}] {status:4} '{label[:55]}'")
        if best_answer:
            print(f"         pattern: '{best_pattern}'")
            print(f"         answer:  '{best_answer[:70]}'")
            if options:
                if chosen_option:
                    print(f"         option:  '{chosen_option}'  ✓")
                else:
                    print(f"         option:  ** NO MATCH in {len(options)} options **  ✗")
                    print(f"         available: {options[:5]}")
        else:
            if options:
                print(f"         options: {options[:5]}")
            print(f"         ** NEEDS ANSWER **")

        print()

    print(f"{'='*90}")
    print(f"SUMMARY: {matched} matched, {unmatched} unmatched, {skipped} skipped")
    print(f"{'='*90}")


if __name__ == "__main__":
    main()
