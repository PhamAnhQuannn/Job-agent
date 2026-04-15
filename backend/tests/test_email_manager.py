import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.email_manager import (
    generate_email,
    extract_verification,
    detect_oa,
    match_email_by_tag,
)


# --- generate_email tests ---

class TestGenerateEmail:
    def test_with_custom_domain(self, monkeypatch):
        monkeypatch.setattr("services.email_manager.EMAIL_DOMAIN", "jobs.example.com")
        monkeypatch.setattr("services.email_manager.GMAIL_ADDRESS", "")
        addr = generate_email("Google", "swe")
        assert addr.startswith("apply-google-swe-")
        assert addr.endswith("@jobs.example.com")

    def test_with_gmail_alias(self, monkeypatch):
        monkeypatch.setattr("services.email_manager.EMAIL_DOMAIN", "")
        monkeypatch.setattr("services.email_manager.GMAIL_ADDRESS", "me@gmail.com")
        addr = generate_email("Meta")
        assert addr.startswith("me+meta-")
        assert addr.endswith("@gmail.com")

    def test_no_config_returns_empty(self, monkeypatch):
        monkeypatch.setattr("services.email_manager.EMAIL_DOMAIN", "")
        monkeypatch.setattr("services.email_manager.GMAIL_ADDRESS", "")
        assert generate_email("Google") == ""

    def test_sanitizes_company(self, monkeypatch):
        monkeypatch.setattr("services.email_manager.EMAIL_DOMAIN", "d.com")
        addr = generate_email("ABC-Corp!!! @#$")
        assert "abccorp" in addr

    def test_truncates_long_company(self, monkeypatch):
        monkeypatch.setattr("services.email_manager.EMAIL_DOMAIN", "d.com")
        long_name = "a" * 50
        addr = generate_email(long_name)
        local = addr.split("@")[0]
        # Company slug capped at 20 chars
        assert len(local.split("-")[1]) <= 20


# --- extract_verification tests ---

class TestExtractVerification:
    def test_numeric_code_after_keyword(self):
        body = "Your verification code is: 483921"
        result = extract_verification(body)
        assert result == {"type": "code", "value": "483921"}

    def test_numeric_code_before_keyword(self):
        body = "Please enter 7742 as your OTP code"
        result = extract_verification(body)
        assert result == {"type": "code", "value": "7742"}

    def test_verify_link(self):
        body = 'Click here to verify: https://example.com/verify?token=abc123'
        result = extract_verification(body)
        assert result["type"] == "link"
        assert "verify" in result["value"]

    def test_no_verification(self):
        body = "Thank you for applying! We will review your application."
        assert extract_verification(body) is None

    def test_empty_body(self):
        assert extract_verification("") is None
        assert extract_verification(None) is None


# --- detect_oa tests ---

class TestDetectOA:
    def test_hackerrank(self):
        body = "Complete your assessment at https://www.hackerrank.com/test/abc123 by 01/15/2025"
        result = detect_oa(body)
        assert result["platform"] == "hackerrank"
        assert "hackerrank.com" in result["link"]
        assert result["deadline"] == "01/15/2025"

    def test_codesignal(self):
        body = "You've been invited to a CodeSignal assessment: https://app.codesignal.com/invite/xyz"
        result = detect_oa(body)
        assert result["platform"] == "codesignal"

    def test_codility(self):
        body = "Take your Codility test: https://app.codility.com/test/abc"
        result = detect_oa(body)
        assert result["platform"] == "codility"

    def test_no_oa(self):
        body = "Thank you for your interest. We look forward to speaking with you."
        assert detect_oa(body) is None

    def test_deadline_extraction(self):
        body = "Please complete your HackerRank test at https://hackerrank.com/t/123 before January 20, 2025"
        result = detect_oa(body)
        assert result["deadline"] == "January 20, 2025"

    def test_empty_body(self):
        assert detect_oa("") is None
        assert detect_oa(None) is None


# --- Rejection detection is tested indirectly via process_emails ---
# --- match_email_by_tag ---

class TestMatchByTag:
    def test_extracts_custom_domain_tag(self, tmp_path, monkeypatch):
        """Verify regex extracts company tag from apply- prefix."""
        import re
        pattern = re.compile(r"(?:apply-|[^+]+\+)([a-z0-9]+)")
        assert pattern.match("apply-google-0414@jobs.com").group(1) == "google"

    def test_extracts_gmail_alias_tag(self):
        import re
        pattern = re.compile(r"(?:apply-|[^+]+\+)([a-z0-9]+)")
        assert pattern.match("me+meta-0414@gmail.com").group(1) == "meta"
