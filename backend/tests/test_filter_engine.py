import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.filter_engine import score_job, compute_dedup_hash, filter_job


# === GATE TESTS ===

def test_gate_intern_required():
    """Title without intern/internship/co-op → SKIP"""
    r = score_job("Software Engineer", "Java, Python, SQL", "San Francisco, CA")
    assert r["decision"] == "SKIP"
    assert r["hard_skip"] is True
    assert "intern" in r["hard_skip_reason"]


def test_gate_swe_required():
    """Title with intern but no SWE keyword → SKIP"""
    r = score_job("Marketing Intern", "Python, SQL, Excel", "New York, NY")
    assert r["decision"] == "SKIP"
    assert r["hard_skip"] is True
    assert "software engineer" in r["hard_skip_reason"]


def test_gate_us_location_required():
    """Non-US location → SKIP"""
    r = score_job("Software Engineer Intern", "Java, Python, SQL", "London, UK")
    assert r["decision"] == "SKIP"
    assert r["hard_skip"] is True
    assert "non-US" in r["hard_skip_reason"]


def test_gate_us_state_name():
    """Full state name recognized as US"""
    r = score_job("Software Engineer Intern", "Java, Python", "California")
    assert r["hard_skip"] is False


def test_gate_us_state_abbrev():
    """State abbreviation recognized as US"""
    r = score_job("Software Engineer Intern", "Java, Python", "San Francisco, CA")
    assert r["hard_skip"] is False


def test_gate_remote_is_us():
    """Remote location passes US gate"""
    r = score_job("Software Engineer Intern", "Java, Python", "Remote")
    assert r["hard_skip"] is False


def test_gate_no_location_passes():
    """No location listed → passes US gate"""
    r = score_job("Software Engineer Intern", "Java, Python", None)
    assert r["hard_skip"] is False


def test_gate_non_us_countries():
    """Various non-US locations → SKIP"""
    for loc in ["Amsterdam, Netherlands", "Bengaluru, India", "Toronto, Canada", "Berlin, Germany"]:
        r = score_job("Software Engineer Intern", "Java, Python, SQL", loc)
        assert r["decision"] == "SKIP", f"Should skip {loc}"


# === SCORING TESTS (all pass gates) ===

def test_swe_intern_auto_apply():
    """Software Engineer Intern with strong skills → AUTO APPLY"""
    r = score_job("Software Engineer Intern", "Java, Python, SQL, Docker", "New York, NY")
    assert r["decision"] == "AUTO_APPLY"
    assert r["score"] >= 3


def test_backend_intern_auto_apply():
    """Backend Engineer Intern → AUTO_APPLY with backend bonus"""
    r = score_job("Backend Engineer Intern", "Java, Spring Boot, SQL, Docker", "CA")
    assert r["decision"] == "AUTO_APPLY"
    assert any("backend" in t for t in r["matched_title"])


def test_swe_intern_minimal_review():
    """SWE Intern with no description → REVIEW (base score from gates)"""
    r = score_job("Software Engineer Intern", "", "CA")
    assert r["decision"] == "REVIEW"


def test_web_developer_intern_passes():
    """Web Developer Intern → passes gates"""
    r = score_job("Web Developer Intern", "Java, Python, SQL", "CA")
    assert r["hard_skip"] is False
    assert r["decision"] in ("AUTO_APPLY", "REVIEW")


def test_developer_ecosystem_rejected():
    """Developer Ecosystem is not a SWE role → SKIP"""
    r = score_job("Technical Video Content Intern, Developer Ecosystem", "Python, SQL", "Remote - US")
    assert r["decision"] == "SKIP"
    assert "software engineer" in r["hard_skip_reason"]


def test_coop_passes_gate():
    """Co-op passes intern gate"""
    r = score_job("Software Engineer Co-op", "Java, Python", "CA")
    assert r["hard_skip"] is False


# === HARD SKIP TESTS ===

def test_citizenship_hard_skip():
    """U.S. citizen required → hard skip"""
    r = score_job("Software Engineer Intern", "U.S. citizen required. Java.", "CA")
    assert r["hard_skip"] is True


def test_no_sponsorship_hard_skip():
    """No sponsorship → hard skip"""
    r = score_job("Software Engineer Intern", "No sponsorship available.", "CA")
    assert r["hard_skip"] is True


def test_security_clearance_hard_skip():
    """Security clearance → hard skip"""
    r = score_job("Software Engineer Intern", "Top secret clearance required.", "CA")
    assert r["hard_skip"] is True


def test_return_to_school_hard_skip():
    """Must return to school → hard skip"""
    r = score_job("Software Engineer Intern", "Must return to school after internship.", "CA")
    assert r["hard_skip"] is True


def test_currently_enrolled_ok():
    """Currently enrolled → NOT skipped"""
    r = score_job("SWE Intern", "Must be currently enrolled. Python, SQL.", "CA")
    assert r["hard_skip"] is False


def test_returning_to_school_hard_skip():
    """Returning to school → hard skip"""
    r = score_job("Backend Engineer Intern", "Must be returning to school in Fall 2026.", "CA")
    assert r["hard_skip"] is True


def test_graduation_after_may_2026_skip():
    """Graduation Dec 2026 → skip"""
    r = score_job("Software Engineer Intern", "Expected graduation December 2026.", "CA")
    assert r["hard_skip"] is True


def test_graduation_2027_skip():
    """Graduation 2027 → skip"""
    r = score_job("SWE Intern", "Graduating in 2027. Python, SQL.", "CA")
    assert r["hard_skip"] is True


def test_graduation_may_2026_ok():
    """Graduation May 2026 → NOT skipped"""
    r = score_job("Software Engineer Intern", "Expected graduation by May 2026. Java.", "CA")
    assert r["hard_skip"] is False


def test_semester_remaining_skip():
    """At least one semester remaining → skip"""
    r = score_job("Software Engineer Intern", "At least one semester remaining.", "CA")
    assert r["hard_skip"] is True


def test_phd_intern_skip():
    """PhD intern → SKIP"""
    r = score_job("[2026] Software Engineer, PhD Intern", "Python, SQL", "San Mateo, CA")
    assert r["hard_skip"] is True
    assert "phd" in r["hard_skip_reason"]


def test_masters_intern_skip():
    """Master's level intern → SKIP"""
    r = score_job("Software Engineer Intern, Masters", "Java, Python", "CA")
    assert r["hard_skip"] is True
    assert "master" in r["hard_skip_reason"]


def test_staff_skip():
    """Staff engineer intern → SKIP"""
    r = score_job("Staff Software Engineer Intern", "Java, Python", "CA")
    assert r["hard_skip"] is True
    assert "staff" in r["hard_skip_reason"]


def test_lead_skip():
    """Lead engineer → SKIP"""
    r = score_job("Lead Software Engineer Intern", "Java, Python", "CA")
    assert r["hard_skip"] is True
    assert "lead" in r["hard_skip_reason"]


def test_masters_degree_required_skip():
    """Description requires master's degree → SKIP"""
    r = score_job("Software Engineer Intern", "Master's degree required. Java, Python.", "CA")
    assert r["hard_skip"] is True


def test_advanced_degree_required_skip():
    """Description requires advanced degree → SKIP"""
    r = score_job("Software Engineer Intern", "Advanced degree required. Python, SQL.", "CA")
    assert r["hard_skip"] is True


def test_bachelors_ok():
    """Bachelor's degree mentioned → NOT skipped"""
    r = score_job("Software Engineer Intern", "Bachelor's degree in CS. Java, Python, SQL", "CA")
    assert r["hard_skip"] is False


def test_skillbridge_skip():
    """SkillBridge intern → SKIP"""
    r = score_job("Software Engineer-SkillBridge Intern", "Python", "Remote - USA")
    assert r["hard_skip"] is True
    assert "skillbridge" in r["hard_skip_reason"].lower()


def test_non_us_in_title_skip():
    """Title says France even if location says NY → SKIP"""
    r = score_job("Software Engineer, Internship - France", "Java, Python", "New York, NY")
    assert r["hard_skip"] is True
    assert "france" in r["hard_skip_reason"]


def test_apprenticeship_skip():
    """Apprenticeship in title → SKIP"""
    r = score_job("Software Engineer, Community Apprenticeship - Intern", "Python", "CA")
    assert r["hard_skip"] is True
    assert "apprenticeship" in r["hard_skip_reason"]


# === NEGATIVE KEYWORD TESTS ===

def test_mechanical_skip():
    """Mechanical Engineer → SKIP (fails SWE gate)"""
    r = score_job("Mechanical Engineer", "CAD, SolidWorks, AutoCAD", "CA")
    assert r["decision"] == "SKIP"


def test_robotics_skip():
    """Robotics role fails SWE gate"""
    r = score_job("Robotics Engineer", "embedded systems, firmware", "CA")
    assert r["decision"] == "SKIP"


# === WORD BOUNDARY TESTS ===

def test_java_not_javascript():
    """'java' must NOT match 'javascript'"""
    r = score_job("Software Engineer Intern", "javascript, react, html, css", "CA")
    assert "java" not in r["matched_positive"]
    assert "javascript" in r["matched_positive"]


# === DEDUP TESTS ===

def test_dedup_hash():
    """Same company + title + location = same hash"""
    h1 = compute_dedup_hash("Google", "Software Engineer Intern", "Mountain View, CA")
    h2 = compute_dedup_hash("Google", "Software Engineer Intern", "Mountain View, CA")
    h3 = compute_dedup_hash("Google", "Software Engineer Intern", "New York, NY")
    assert h1 == h2
    assert h1 != h3


# === FILTER_JOB INTEGRATION TEST ===

def test_filter_job_auto_apply():
    """filter_job returns AUTO_APPLY for SWE Intern in US with skills"""
    result = filter_job("Google", "Software Engineer Intern", "CA", "Java, Python, SQL, Docker, AWS")
    assert result["status"] == "AUTO_APPLY"
    assert len(result["dedup_hash"]) == 16


def test_filter_job_skips_non_us():
    """filter_job skips non-US jobs"""
    result = filter_job("Google", "Software Engineer Intern", "London, UK", "Java, Python")
    assert result["status"] == "SKIPPED"


def test_filter_job_skips_non_intern():
    """filter_job skips non-intern titles"""
    result = filter_job("Google", "Senior Software Engineer", "CA", "Java, Python")
    assert result["status"] == "SKIPPED"
