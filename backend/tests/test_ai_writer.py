import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.pdf_export import save_cover_letter_pdf


def test_pdf_generation():
    """Cover letter PDF is created and is a valid file."""
    letter = (
        "I am excited to apply for the Software Engineer Intern position at Google. "
        "With experience in Java, Python, and building real-time applications using "
        "Next.js and Socket.IO, I am confident I can contribute to your team. "
        "My project VOCO, a real-time emergency dispatch dashboard, demonstrates my "
        "ability to work with modern web technologies at scale. I look forward to "
        "discussing how my skills align with this role."
    )
    path = save_cover_letter_pdf(letter, "Google", "Software Engineer Intern", "Quan Pham")

    assert os.path.exists(path)
    assert path.endswith(".pdf")
    assert os.path.getsize(path) > 500  # Not empty

    # Verify filename is sanitized
    assert "Google" in os.path.basename(path)
    assert " " not in os.path.basename(path)

    # Cleanup
    os.remove(path)


def test_pdf_special_characters():
    """PDF handles company names with special characters."""
    letter = "Test cover letter content for a role at this company."
    path = save_cover_letter_pdf(letter, "O'Reilly & Co.", "SWE Intern", "Quan Pham")

    assert os.path.exists(path)
    assert os.path.getsize(path) > 500
    os.remove(path)


def test_pdf_long_letter():
    """PDF handles a longer cover letter with multiple paragraphs."""
    letter = (
        "First paragraph about why I am interested in this company.\n\n"
        "Second paragraph about my technical skills including Java, Spring Boot, "
        "Python, Django, TypeScript, React, and Next.js. I have built multiple "
        "full-stack applications and contributed to team projects.\n\n"
        "Third paragraph about my specific experience with the VOCO project and "
        "how it demonstrates my ability to work with real-time systems, APIs, "
        "and cloud infrastructure. I look forward to hearing from you."
    )
    path = save_cover_letter_pdf(letter, "Meta", "Backend Engineer Intern", "Quan Pham")

    assert os.path.exists(path)
    assert os.path.getsize(path) > 500
    os.remove(path)
