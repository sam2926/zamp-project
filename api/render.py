"""Render a page of an uploaded PDF to a PNG, for the review viewer.

The reviewer needs to see the actual invoice with our guess boxed on it — that is the moment
the extraction becomes checkable. PyMuPDF rasterises straight from the bytes we already hold
in memory, so there is no second copy of the file on disk.
"""
from __future__ import annotations


def render_page(pdf_bytes: bytes, page: int = 0, width: int = 1200) -> bytes:
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = max(0, min(page, doc.page_count - 1))
        sheet = doc[page]
        zoom = max(0.1, width / sheet.rect.width)
        pix = sheet.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")
    finally:
        doc.close()
