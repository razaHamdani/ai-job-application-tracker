import io

from pypdf import PdfWriter

from app.resumes.services import extract_text_from_pdf


def test_extract_text_from_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)

    text = extract_text_from_pdf(buffer)
    assert isinstance(text, str)
