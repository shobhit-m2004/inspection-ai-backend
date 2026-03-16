from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


class DocumentParseError(Exception):
    pass


def extract_text_from_file(path: str | Path) -> str:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in {'.txt', '.log', '.csv', '.md'}:
        return file_path.read_text(encoding='utf-8', errors='ignore')

    if suffix == '.pdf':
        return extract_text_from_pdf(file_path)

    if suffix == '.docx':
        return extract_text_from_docx(file_path)

    raise DocumentParseError(f'Unsupported file type: {suffix}')


def extract_text_from_pdf(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    text_parts: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ''
        if page_text.strip():
            text_parts.append(f'\n[page_{i}]\n{page_text.strip()}')
    return '\n'.join(text_parts).strip()


def extract_text_from_docx(file_path: Path) -> str:
    doc = DocxDocument(str(file_path))
    return '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
