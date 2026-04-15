import os
from fpdf import FPDF

COVER_LETTER_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cover_letters")


def save_cover_letter_pdf(
    letter_text: str,
    company: str,
    role_title: str,
    applicant_name: str,
) -> str:
    """Save a cover letter as a PDF file.

    Returns the file path of the saved PDF.
    """
    os.makedirs(COVER_LETTER_DIR, exist_ok=True)

    # Sanitize filename
    safe_company = "".join(c if c.isalnum() or c in " -_" else "" for c in company).strip()
    safe_role = "".join(c if c.isalnum() or c in " -_" else "" for c in role_title).strip()
    filename = f"CoverLetter_{safe_company}_{safe_role}.pdf".replace(" ", "_")
    filepath = os.path.join(COVER_LETTER_DIR, filename)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)

    # Header — applicant name
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, applicant_name, new_x="LMARGIN", new_y="NEXT")

    # Thin line
    pdf.set_draw_color(180, 180, 180)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Company + role
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"{role_title} at {company}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Body
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, letter_text)

    pdf.output(filepath)
    return filepath
