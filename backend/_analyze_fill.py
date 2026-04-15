"""Analyze scan fields vs answer bank — full fill plan preview."""
import json
from database import get_connection

c = get_connection()
rows = c.execute(
    "SELECT question_pattern, answer FROM answer_bank ORDER BY length(question_pattern) DESC"
).fetchall()

fields = json.load(open("data/screenshots/last_scan.json", "r", encoding="utf-8"))
print(f"Answer bank: {len(rows)} entries")
print(f"Scan fields: {len(fields)} fields\n")

for i, f in enumerate(fields, 1):
    label = f["label"]
    text_lower = label.lower()
    best = None
    best_len = 0
    for r in rows:
        pat = r["question_pattern"].lower()
        if pat in text_lower and len(pat) > best_len:
            best = r
            best_len = len(pat)

    cv = f.get("current_value", "")
    if cv:
        status = "SKIP"
    elif f.get("is_conditional"):
        status = "COND"
    elif best:
        status = "OK"
    else:
        status = "MISS"

    ans = best["answer"][:60] if best else ""
    pat = best["question_pattern"][:45] if best else ""
    print(f"[{i:2d}] {status:4s} | {label[:55]:55s}")
    if cv:
        print(f"          pre-filled: {cv[:40]}")
    if best:
        print(f"          pat: {pat}")
        print(f"          ans: {ans}")
    if best and f.get("options"):
        ans_l = best["answer"].lower().strip()
        matched = None
        for opt in f["options"]:
            if opt.lower().strip() == ans_l:
                matched = opt
                break
        if not matched:
            for opt in f["options"]:
                ol = opt.lower()
                if ans_l.startswith("yes") and ol.startswith("yes"):
                    matched = opt; break
                if ans_l.startswith("no") and ol.startswith("no"):
                    matched = opt; break
                if ans_l in ol or ol in ans_l:
                    matched = opt; break
        if matched:
            print(f"          option: '{matched}'  OK")
        else:
            opts_preview = f["options"][:5]
            print(f"          option: ** NO MATCH ** from {opts_preview}")
    if status == "MISS":
        req = "*" in label
        print(f"          {'REQUIRED - NEEDS ANSWER' if req else '(optional, will skip)'}")
    print()

c.close()
