"""Claim verification — full document context aware."""

from __future__ import annotations

from typing import Any, Callable

from services.llm_service import LLMService
from services.search_service import SearchService
from utils.constants import STATUS_UNVERIFIABLE

ProgressCallback = Callable[[int, int], None]


class Verifier:
    """
    Verify extracted claims against live web evidence,
    with the full document context passed to every LLM call.
    """

    def __init__(self, model: str | None = None):
        self.llm = LLMService(model=model)
        self.search = SearchService()

    def verify_claims(
        self,
        claims: list[dict[str, str]],
        doc_summary: str = "",
        progress_callback: ProgressCallback | None = None,
        min_confidence: int = 0,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Verify every claim in the list.

        doc_summary  — full-document factual summary produced during extraction.
                       Passed to each LLM verification call so the model can
                       cross-reference claims against the source document.
        """
        if not claims:
            return [], "No claims to verify."

        results: list[dict[str, Any]] = []
        total = len(claims)

        for idx, claim_data in enumerate(claims):
            if progress_callback:
                progress_callback(idx, total)
            result = self._verify_one(claim_data, doc_summary)
            if result.get("confidence", 0) >= min_confidence:
                results.append(result)

        if progress_callback:
            progress_callback(total, total)

        return results, None

    # ── Private ───────────────────────────────────────────────────────────

    def _verify_one(
        self, claim_data: dict[str, str], doc_summary: str
    ) -> dict[str, Any]:
        claim = claim_data.get("claim", "").strip()
        ctype = claim_data.get("type", "Other")

        result: dict[str, Any] = {
            "claim": claim,
            "type": ctype,
            "status": STATUS_UNVERIFIABLE,
            "confidence": 0,
            "explanation": "Verification did not complete.",
            "key_finding": "",
            "sources": [],
            "search_query": "",
            "evidence_snippet": "",
        }

        # Step 1 — web search for external evidence
        bundle, search_err = self.search.search_claim(claim)
        result["search_query"] = bundle.get("query", "")
        result["sources"] = bundle.get("sources", [])
        evidence = bundle.get("evidence", "")
        result["evidence_snippet"] = evidence[:1000]

        if search_err:
            result["explanation"] = f"Search failed: {search_err}"
            return result

        if not evidence.strip():
            result["explanation"] = "No external web evidence found for this claim."
            return result

        # Step 2 — LLM verification with document context + web evidence
        verification, _ = self.llm.verify_claim(
            claim=claim,
            evidence=evidence,
            doc_summary=doc_summary,
        )
        result.update(verification)
        return result
