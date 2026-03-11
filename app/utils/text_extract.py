import io
from typing import Optional

try:
    import pypdf
except Exception:
    pypdf = None
try:
    import pandas as pd
except Exception:
    pd = None


def extract_text_from_upload(filename: str, content_bytes: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf") and pypdf:
        reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n".join(pages).strip()

    if name.endswith((".xlsx", ".xls")):
        if not pd:
            raise ValueError("Excel support requires pandas and openpyxl")
        with io.BytesIO(content_bytes) as buff:
            sheets = pd.read_excel(buff, sheet_name=None)
        parts = []
        for _, df in sheets.items():
            parts.append(df.to_csv(index=False))
        return "\n".join(parts).strip()

    # For txt/csv or when pypdf is unavailable
    return content_bytes.decode("utf-8", errors="ignore").strip()
