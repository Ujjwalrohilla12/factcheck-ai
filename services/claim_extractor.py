"""Claim extraction — full document context aware."""

from __future__ import annotations

from services.llm_service import LLMService
from utils.constants import CLAIM_TYPES
from utils.helpers import clean_claim_text, remove_duplicate_claims


class ClaimExtractor:
    """
    Extract every verifiable factual claim from a document.

    Strategy:
    1. Build a full-document summary (≤ 300 words) from the complete text.
    2. Split the full text into overlapping chunks.
    3. For each chunk, pass BOTH the chunk text AND the document summary
       to the LLM so claims are resolved in full context.
    4. Deduplicate and validate across all chunks.
    """

    def __init__(self, model: str | None = None):
        self.llm = LLMService(model=model)

    def extract_and_process_claims(
        self,
        text: str,
        remove_duplicates: bool = True,
        max_claims: int = 100,
    ) -> tuple[list[dict[str, str]], str | None]:
        if not text or len(text.strip()) < 50:
            return [], "Text is too short to extract meaningful claims."

        # Step 1: summarise the full document for context injection
        doc_summary = self.llm.summarise_document(text)

        # Step 2: extract from every chunk with document context
        all_claims: list[dict[str, str]] = []
        errors: list[str] = []

        chunks = self._chunk_text(text)
        for chunk in chunks:
            claims, error = self.llm.extract_claims(chunk, doc_summary=doc_summary)
            if error:
                errors.append(error)
            all_claims.extend(claims)

        # Step 3: validate and deduplicate
        cleaned = self._validate(all_claims)
        if remove_duplicates:
            cleaned = remove_duplicate_claims(cleaned)

        if not cleaned and errors:
            return [], " | ".join(sorted(set(errors)))

        return cleaned[:max_claims], None

    # ── Private ───────────────────────────────────────────────────────────

    @staticmethod
    def _chunk_text(
        text: str,
        chunk_size: int = 6000,
        overlap: int = 600,
        max_chunks: int = 20,
    ) -> list[str]:
        """
        Split text into overlapping chunks.
        No artificial cap on document length — process as many chunks as needed
        up to max_chunks to cover the full document.
        """
        text = text.strip()
        chunks: list[str] = []
        start = 0
        while start < len(text) and len(chunks) < max_chunks:
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = end - overlap
        return chunks

    @staticmethod
    def _validate(claims: list[dict[str, str]]) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for item in claims:
            claim = clean_claim_text(str(item.get("claim", "")))
            ctype = str(item.get("type", "Other")).strip()
            if len(claim) < 15 or len(claim) > 700:
                continue
            if ctype not in CLAIM_TYPES:
                ctype = "Other"
            out.append({"claim": claim, "type": ctype})
        return out
