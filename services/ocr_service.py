"""OCR service using Google Gemini Vision API for scanned PDFs."""

from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path

import fitz
import google.generativeai as genai
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Ordered fallback list — confirmed available models
_MODELS = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-flash-lite-latest"]


class OCRService:
    """Extract text from scanned PDFs using Gemini Vision API."""

    def __init__(self):
        load_dotenv(dotenv_path=_ENV_PATH, override=True)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key.strip() in ("", "your_gemini_api_key_here"):
            raise ValueError(
                "GEMINI_API_KEY not configured. "
                "Add it to your .env file. "
                "Get a key at https://aistudio.google.com/app/apikey"
            )
        if not (api_key.startswith("AIza") or api_key.startswith("AQ.")):
            raise ValueError(
                "GEMINI_API_KEY format is invalid. "
                "Valid keys start with 'AIza' or 'AQ.'. "
                "Get a key at https://aistudio.google.com/app/apikey"
            )
        genai.configure(api_key=api_key)

    # ── Public ────────────────────────────────────────────────────────────

    def extract_text_from_scanned_pdf(self, pdf_bytes: bytes) -> tuple[str, str | None]:
        """Convert each page to a PNG and extract text via Gemini Vision."""
        try:
            parts: list[str] = []
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    img_b64 = self._page_to_b64(page)
                    prompt = (
                        "Extract all text from this PDF page image exactly as it appears. "
                        "Preserve layout, columns, and table structure. "
                        "Return only the extracted text — no commentary."
                    )
                    response = self._call([prompt, {"mime_type": "image/png", "data": img_b64}])
                    text = response.text.strip()
                    if text:
                        parts.append(f"\n\n--- Page {page_num + 1} ---\n{text}")

            result = "\n".join(parts)
            if len(result.strip()) < 50:
                return "", "OCR could not extract sufficient text from this PDF."
            return result, None

        except ValueError as exc:
            return "", str(exc)
        except Exception as exc:
            return "", f"OCR processing error: {exc}"

    def extract_tables_from_scanned_pdf(
        self, pdf_bytes: bytes
    ) -> tuple[list[dict], str | None]:
        """Extract structured tables from each page via Gemini Vision."""
        tables: list[dict] = []
        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    img_b64 = self._page_to_b64(page)
                    prompt = (
                        "Extract all tables from this page as a JSON array. "
                        "Each table: {\"headers\": [...], \"rows\": [[...]]}. "
                        "Return [] if no tables found. Return ONLY valid JSON."
                    )
                    response = self._call([prompt, {"mime_type": "image/png", "data": img_b64}])
                    try:
                        data = json.loads(response.text.strip())
                        for tbl in data:
                            tbl["page"] = page_num + 1
                            tables.append(tbl)
                    except Exception:
                        pass
            return tables, None
        except Exception as exc:
            return [], f"Table extraction error: {exc}"

    # ── Private ───────────────────────────────────────────────────────────

    @staticmethod
    def _page_to_b64(page) -> str:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        return base64.standard_b64encode(pix.tobytes(output="png")).decode()

    def _call(self, payload, retries: int = 3):
        """Try each model with exponential backoff on 429, skip on 404."""
        last_exc: Exception = RuntimeError("No models available.")
        for model_name in _MODELS:
            model = genai.GenerativeModel(model_name)
            for attempt in range(retries):
                try:
                    return model.generate_content(payload)
                except Exception as exc:
                    msg = str(exc)
                    if "429" in msg:
                        if attempt < retries - 1:
                            time.sleep(2 ** attempt)
                            continue
                        last_exc = exc
                        break  # try next model
                    if "404" in msg or "not found" in msg.lower():
                        last_exc = exc
                        break  # try next model
                    raise  # any other error — surface immediately
        raise last_exc
