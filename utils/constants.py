"""Application constants for FactCheck AI."""

from __future__ import annotations

import os

APP_NAME = "FactCheck AI"
MAX_PDF_SIZE_MB = 25
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024

SEARCH_RESULTS_COUNT = int(os.getenv("SEARCH_RESULTS_COUNT", "5"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
SUPPORTED_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1"]
LLM_TEMPERATURE = 0.1
CLAIM_EXTRACTION_TEMPERATURE = 0.0

STATUS_VERIFIED = "Verified"
STATUS_INACCURATE = "Inaccurate"
STATUS_FALSE = "False"
STATUS_UNVERIFIABLE = "Unverifiable"

VALID_STATUSES = [STATUS_VERIFIED, STATUS_INACCURATE, STATUS_FALSE, STATUS_UNVERIFIABLE]

STATUS_COLORS = {
    STATUS_VERIFIED: "#10b981",
    STATUS_INACCURATE: "#f97316",
    STATUS_FALSE: "#ef4444",
    STATUS_UNVERIFIABLE: "#6b7280",
}

CLAIM_TYPES = [
    "Market Statistic",
    "Financial Number",
    "User Count",
    "Growth Rate",
    "Date",
    "Technical Figure",
    "Technical Specification",
    "Revenue",
    "Percentage",
    "Named Entity",
    "Product / Service",
    "Legal / Regulatory",
    "Geographic",
    "Other",
]

ERROR_FILE_SIZE = f"File size exceeds the {MAX_PDF_SIZE_MB} MB limit."
ERROR_FILE_TYPE = "Please upload a valid PDF file."
ERROR_INVALID_PDF = (
    "No extractable text found. "
    "The PDF may be empty, corrupted, or a scanned image without OCR support."
)
ERROR_API_KEY = (
    "Missing API configuration. "
    "Set OPENAI_API_KEY and TAVILY_API_KEY in your .env file."
)

# ── Extraction prompts ────────────────────────────────────────────────────────

DOCUMENT_SUMMARY_SYSTEM_PROMPT = (
    "You are a document analyst. "
    "Read the full document text and produce a concise factual summary "
    "(max 300 words) covering: topic, key entities, main arguments, "
    "important numbers, dates, and conclusions. "
    "Respond with plain text only — no JSON, no headers."
)

DOCUMENT_SUMMARY_USER_PROMPT = """\
Summarise the key facts in this document in 300 words or less.

DOCUMENT:
{text}"""

CLAIM_EXTRACTION_SYSTEM_PROMPT = (
    "You are a comprehensive fact-extraction assistant working on a complete document. "
    "Your job is to extract EVERY checkable factual claim from the given section, "
    "informed by the full document context provided. "
    "Extract ALL of the following types of claims:\n"
    "  - Numbers, statistics, percentages, financial figures\n"
    "  - Dates and timelines\n"
    "  - Named people, companies, products, and places and what is claimed about them\n"
    "  - Market sizes, growth rates, user/customer counts\n"
    "  - Technical specifications and capabilities\n"
    "  - Legal, regulatory, or compliance statements\n"
    "  - Cause-and-effect or factual relationship claims\n"
    "  - Any other concrete, verifiable assertion\n"
    "Do NOT skip a claim just because it seems obvious. "
    "Do NOT include pure opinions, future predictions, or vague marketing copy. "
    "You MUST respond with valid JSON only — no prose, no markdown fences."
)

CLAIM_EXTRACTION_USER_PROMPT = """\
DOCUMENT CONTEXT (full document summary for reference):
{doc_summary}

SECTION TO EXTRACT FROM:
{text}

Extract every verifiable factual claim from the section above.
Use the document context to resolve any ambiguous references (e.g. "the company", "the product").

Respond with ONLY this JSON — nothing else:
{{"claims": [{{"claim": "complete self-contained factual statement", "type": "Market Statistic"}}]}}

Valid type values:
Market Statistic, Financial Number, User Count, Growth Rate, Date,
Technical Figure, Technical Specification, Revenue, Percentage,
Named Entity, Product / Service, Legal / Regulatory, Geographic, Other"""

# ── Verification prompts ──────────────────────────────────────────────────────

VERIFICATION_SYSTEM_PROMPT = (
    "You are a rigorous fact-checking analyst. "
    "You receive a claim, a summary of the source document it came from, "
    "and external web evidence. "
    "Your task is to determine whether the claim is accurate by comparing it against "
    "BOTH the document context AND the external evidence. "
    "Classify the claim as exactly one of:\n"
    "  Verified   — external evidence directly and credibly supports the claim\n"
    "  Inaccurate — claim is partially correct but materially outdated, incomplete, "
    "               or contradicted by more recent / authoritative data\n"
    "  False      — external evidence directly contradicts the claim, or the claim "
    "               is specific but completely unsupported by any credible source\n"
    "  Unverifiable — evidence is genuinely insufficient to make a determination\n"
    "Always prefer Verified or False over Unverifiable when evidence is present. "
    "You MUST respond with valid JSON only — no prose, no markdown fences."
)

VERIFICATION_USER_PROMPT = """\
CLAIM TO VERIFY:
{claim}

SOURCE DOCUMENT CONTEXT:
{doc_summary}

EXTERNAL WEB EVIDENCE:
{evidence}

Respond with ONLY this JSON — nothing else:
{{"status": "Verified", "confidence": 85, "explanation": "Two sentences grounded in the evidence and document context.", "key_finding": "The single most important supporting or contradicting fact."}}"""
