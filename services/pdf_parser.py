"""PDF parsing service with multiple extraction backends."""

from __future__ import annotations

import io

import fitz
import pdfplumber

from utils.constants import ERROR_INVALID_PDF
from utils.helpers import sanitize_text

_MIN_CHARS = 50


class PDFParser:
    """Extract text and metadata from uploaded PDF files."""

    @staticmethod
    def extract_text(pdf_file) -> tuple[str, str | None]:
        """
        Extract text from a PDF.
        Pipeline: pdfplumber → PyMuPDF → Gemini OCR (scanned PDFs).
        """
        try:
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
        except Exception as exc:
            return "", f"Could not read uploaded file: {exc}"

        # 1. pdfplumber
        text = PDFParser._pdfplumber(pdf_bytes)
        if len(text.strip()) >= _MIN_CHARS:
            return sanitize_text(text), None

        # 2. PyMuPDF
        text = PDFParser._pymupdf(pdf_bytes)
        if len(text.strip()) >= _MIN_CHARS:
            return sanitize_text(text), None

        # 3. Gemini OCR
        ocr_text, ocr_error = PDFParser._ocr(pdf_bytes)
        if ocr_error:
            return "", ocr_error
        if len(ocr_text.strip()) >= _MIN_CHARS:
            return ocr_text, None

        return "", ERROR_INVALID_PDF

    @staticmethod
    def get_pdf_metadata(pdf_file) -> dict:
        """Return basic metadata for display."""
        try:
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            meta: dict = {"pages": 0, "file_size_mb": round(len(pdf_bytes) / 1_048_576, 2)}
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                meta["pages"] = doc.page_count
                meta["title"] = doc.metadata.get("title") or pdf_file.name
            return meta
        except Exception:
            return {"pages": 0, "file_size_mb": 0}

    # ── Extraction backends ───────────────────────────────────────────────

    @staticmethod
    def _pdfplumber(pdf_bytes: bytes) -> str:
        parts: list[str] = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for i, page in enumerate(pdf.pages, 1):
                    t = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                    if t.strip():
                        parts.append(f"\n\n--- Page {i} ---\n{t}")
        except Exception:
            return ""
        return "\n".join(parts)

    @staticmethod
    def _pymupdf(pdf_bytes: bytes) -> str:
        parts: list[str] = []
        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for i, page in enumerate(doc, 1):
                    t = page.get_text("text") or ""
                    if t.strip():
                        parts.append(f"\n\n--- Page {i} ---\n{t}")
        except Exception:
            return ""
        return "\n".join(parts)

    @staticmethod
    def _ocr(pdf_bytes: bytes) -> tuple[str, str | None]:
        try:
            from services.ocr_service import OCRService
            return OCRService().extract_text_from_scanned_pdf(pdf_bytes)
        except ImportError:
            return "", "OCR service unavailable."
        except Exception as exc:
            return "", f"OCR error: {exc}"
