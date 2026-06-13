"""Shared utility functions."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from utils.constants import (
    ERROR_FILE_SIZE,
    ERROR_FILE_TYPE,
    MAX_PDF_SIZE_BYTES,
    STATUS_FALSE,
    STATUS_INACCURATE,
    STATUS_UNVERIFIABLE,
    STATUS_VERIFIED,
)


def validate_pdf_file(uploaded_file) -> tuple[bool, str | None]:
    """Validate a Streamlit uploaded PDF."""
    if uploaded_file is None:
        return False, "No file provided."
    file_type = getattr(uploaded_file, "type", "")
    file_name = getattr(uploaded_file, "name", "")
    if file_type != "application/pdf" and not file_name.lower().endswith(".pdf"):
        return False, ERROR_FILE_TYPE
    if getattr(uploaded_file, "size", 0) > MAX_PDF_SIZE_BYTES:
        return False, ERROR_FILE_SIZE
    return True, None


def sanitize_text(text: str) -> str:
    """Normalize extracted text while preserving sentence boundaries."""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_json_from_text(text: str, default: Any) -> Any:
    """
    Robustly parse JSON from an LLM response.
    Handles: plain JSON, markdown code fences, leading/trailing prose,
    and single-quoted JSON (common GPT quirk).
    """
    if not text:
        return default

    cleaned = text.strip()

    # Strip markdown code fences  ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    # Attempt 1: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt 2: find the first {...} block (handles leading prose)
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Attempt 3: find the first [...] block
    match = re.search(r"\[[\s\S]*\]", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Attempt 4: replace single quotes with double quotes (last resort)
    try:
        fixed = cleaned.replace("'", '"')
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    return default


def clean_claim_text(claim: str) -> str:
    """Clean a claim string for display and deduplication."""
    claim = re.sub(r"\s+", " ", claim).strip(" -:\t\r\n")
    if claim and claim[-1] not in ".!?":
        claim += "."
    return claim


def remove_duplicate_claims(
    claims: list[dict[str, Any]], threshold: float = 0.88
) -> list[dict[str, Any]]:
    """Remove exact and near-duplicate claims using fuzzy matching."""
    unique: list[dict[str, Any]] = []
    seen: list[str] = []

    for item in claims:
        claim = clean_claim_text(str(item.get("claim", "")))
        normalized = re.sub(r"[^a-z0-9]+", " ", claim.lower()).strip()
        if not normalized:
            continue
        if any(
            normalized == s or SequenceMatcher(None, normalized, s).ratio() >= threshold
            for s in seen
        ):
            continue
        copy = dict(item)
        copy["claim"] = claim
        unique.append(copy)
        seen.append(normalized)

    return unique


def calculate_claim_statistics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return aggregate counts and confidence metrics."""
    total = len(results)
    confidences = [int(r.get("confidence", 0)) for r in results]
    return {
        "total": total,
        "verified": sum(1 for r in results if r.get("status") == STATUS_VERIFIED),
        "inaccurate": sum(1 for r in results if r.get("status") == STATUS_INACCURATE),
        "false": sum(1 for r in results if r.get("status") == STATUS_FALSE),
        "unverifiable": sum(1 for r in results if r.get("status") == STATUS_UNVERIFIABLE),
        "avg_confidence": round(sum(confidences) / total) if total else 0,
    }


def safe_int(value: Any, default: int = 0, lower: int = 0, upper: int = 100) -> int:
    """Coerce a value into a bounded integer."""
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lower, min(upper, n))


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate long text for UI display."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."
