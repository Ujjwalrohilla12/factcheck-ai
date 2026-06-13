"""LLM service — OpenAI primary, Gemini fallback on rate-limit."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIError, OpenAI, RateLimitError

from utils.constants import (
    CLAIM_EXTRACTION_SYSTEM_PROMPT,
    CLAIM_EXTRACTION_TEMPERATURE,
    CLAIM_EXTRACTION_USER_PROMPT,
    DEFAULT_MODEL,
    DOCUMENT_SUMMARY_SYSTEM_PROMPT,
    DOCUMENT_SUMMARY_USER_PROMPT,
    ERROR_API_KEY,
    LLM_TEMPERATURE,
    STATUS_UNVERIFIABLE,
    VALID_STATUSES,
    VERIFICATION_SYSTEM_PROMPT,
    VERIFICATION_USER_PROMPT,
)
from utils.helpers import extract_json_from_text, safe_int

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_GEMINI_MODELS = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-flash-lite-latest"]


class LLMService:
    """OpenAI primary with automatic Gemini fallback on rate-limit."""

    def __init__(self, model: str | None = None):
        load_dotenv(dotenv_path=_ENV_PATH, override=True)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(ERROR_API_KEY)
        self.client = OpenAI(api_key=api_key, timeout=90, max_retries=1)
        self.model = model or DEFAULT_MODEL

    # ── Public ────────────────────────────────────────────────────────────

    def summarise_document(self, text: str) -> str:
        """
        Produce a ≤300-word factual summary of the full document.
        Used as context for claim extraction and verification.
        Falls back to a truncated excerpt if the LLM call fails.
        """
        # Feed the first 30 000 chars — enough for a representative summary
        # without hitting token limits on most models
        excerpt = text.strip()[:30000]
        try:
            summary = self._call(
                system=DOCUMENT_SUMMARY_SYSTEM_PROMPT,
                user=DOCUMENT_SUMMARY_USER_PROMPT.format(text=excerpt),
                temperature=0.0,
                max_tokens=400,
                json_mode=False,
            )
            return summary.strip() or excerpt[:800]
        except Exception:
            # Graceful fallback: use the raw opening of the document
            return excerpt[:800]

    def extract_claims(
        self, text: str, doc_summary: str = ""
    ) -> tuple[list[dict[str, str]], str | None]:
        """
        Extract factual claims from a text chunk.
        doc_summary is injected as full-document context.
        """
        user = CLAIM_EXTRACTION_USER_PROMPT.format(
            doc_summary=doc_summary or "Not available.",
            text=text[:10000],
        )
        try:
            raw = self._call(
                system=CLAIM_EXTRACTION_SYSTEM_PROMPT,
                user=user,
                temperature=CLAIM_EXTRACTION_TEMPERATURE,
                max_tokens=4000,
            )
        except RateLimitError:
            raw = self._gemini_call(CLAIM_EXTRACTION_SYSTEM_PROMPT, user)
        except APIError as exc:
            return [], f"OpenAI API error: {exc}"
        except Exception as exc:
            return [], f"Claim extraction error: {exc}"

        return self._parse_claims(raw)

    def verify_claim(
        self, claim: str, evidence: str, doc_summary: str = ""
    ) -> tuple[dict[str, Any], str | None]:
        """
        Verify a claim against external web evidence AND full document context.
        """
        user = VERIFICATION_USER_PROMPT.format(
            claim=claim,
            doc_summary=doc_summary or "Not available.",
            evidence=evidence[:8000],
        )
        try:
            raw = self._call(
                system=VERIFICATION_SYSTEM_PROMPT,
                user=user,
                temperature=LLM_TEMPERATURE,
                max_tokens=600,
            )
        except RateLimitError:
            raw = self._gemini_call(VERIFICATION_SYSTEM_PROMPT, user)
        except APIError as exc:
            return self._default_result(f"OpenAI API error: {exc}"), None
        except Exception as exc:
            return self._default_result(f"Verification error: {exc}"), None

        return self._parse_verification(raw)

    # ── Core chat helper ──────────────────────────────────────────────────

    def _call(
        self,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool = True,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        kwargs: dict[str, Any] = dict(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self.client.chat.completions.create(**kwargs)
        except APIError as exc:
            # Retry without json_object if model doesn't support it
            if json_mode and (
                "response_format" in str(exc).lower()
                or "json_object" in str(exc).lower()
            ):
                kwargs.pop("response_format", None)
                resp = self.client.chat.completions.create(**kwargs)
            else:
                raise
        return resp.choices[0].message.content or "{}"

    # ── Gemini fallback ───────────────────────────────────────────────────

    def _gemini_call(self, system: str, user: str) -> str:
        try:
            import google.generativeai as genai

            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key or api_key == "your_gemini_api_key_here":
                raise ValueError("GEMINI_API_KEY not configured.")
            genai.configure(api_key=api_key)

            prompt = f"{system}\n\n{user}"
            last_exc: Exception = RuntimeError("No Gemini models available.")

            for model_name in _GEMINI_MODELS:
                for attempt in range(3):
                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(prompt)
                        return response.text or "{}"
                    except Exception as exc:
                        msg = str(exc)
                        if "429" in msg and attempt < 2:
                            time.sleep(2 ** attempt)
                            continue
                        if "429" in msg or "404" in msg or "not found" in msg.lower():
                            last_exc = exc
                            break
                        raise
            raise last_exc

        except Exception as exc:
            return f'{{"error": "{str(exc)[:200]}"}}'

    # ── Parsers ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_claims(raw: str) -> tuple[list[dict[str, str]], str | None]:
        payload = extract_json_from_text(raw, None)

        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("claims") or next(
                (v for v in payload.values() if isinstance(v, list)), []
            )
        else:
            return [], f"Could not parse claims. Response: {raw[:300]}"

        if not isinstance(items, list):
            return [], "Unexpected claims structure from LLM."

        return [
            {
                "claim": str(item.get("claim", "")).strip(),
                "type": str(item.get("type", "Other")).strip(),
            }
            for item in items
            if isinstance(item, dict) and str(item.get("claim", "")).strip()
        ], None

    @staticmethod
    def _parse_verification(raw: str) -> tuple[dict[str, Any], str | None]:
        payload = extract_json_from_text(raw, {})

        if not isinstance(payload, dict):
            return LLMService._default_result("Could not parse verification response."), None

        if payload.get("error"):
            return LLMService._default_result(str(payload["error"])[:200]), None

        status = str(payload.get("status", STATUS_UNVERIFIABLE)).strip()
        if status not in VALID_STATUSES:
            status = STATUS_UNVERIFIABLE

        return {
            "status": status,
            "confidence": safe_int(payload.get("confidence"), default=0),
            "explanation": str(payload.get("explanation", "")).strip(),
            "key_finding": str(payload.get("key_finding", "")).strip(),
        }, None

    @staticmethod
    def _default_result(explanation: str) -> dict[str, Any]:
        return {
            "status": STATUS_UNVERIFIABLE,
            "confidence": 0,
            "explanation": explanation,
            "key_finding": "",
        }
