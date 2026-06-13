"""Tavily web search service."""

from __future__ import annotations

import os
from typing import Any

import requests

from utils.constants import ERROR_API_KEY, REQUEST_TIMEOUT_SECONDS, SEARCH_RESULTS_COUNT

# Simple in-process cache: query → (results, error)
_CACHE: dict[str, tuple[list[dict[str, Any]], str | None]] = {}


class SearchService:
    """Retrieve evidence snippets from Tavily Search API."""

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError(ERROR_API_KEY)

    def search_claim(self, claim: str) -> tuple[dict[str, Any], str | None]:
        """Search Tavily for evidence about a claim and return a formatted bundle."""
        query = f"Verify: {claim}"
        cache_key = f"{self.api_key}::{query}"

        if cache_key in _CACHE:
            raw_results, error = _CACHE[cache_key]
        else:
            raw_results, error = self._search(query)
            _CACHE[cache_key] = (raw_results, error)

        if error:
            return {"query": query, "sources": [], "evidence": ""}, error

        evidence_parts: list[str] = []
        sources: list[dict[str, str]] = []

        for i, result in enumerate(raw_results, start=1):
            title = str(result.get("title") or "Source")
            url = str(result.get("url") or "")
            content = str(result.get("content") or "").strip()
            if not content:
                continue
            evidence_parts.append(
                f"[Source {i}] {title}\nURL: {url or 'N/A'}\n{content[:800]}"
            )
            if url:
                sources.append({"title": title, "url": url})

        return {
            "query": query,
            "sources": sources[:SEARCH_RESULTS_COUNT],
            "evidence": "\n\n".join(evidence_parts),
        }, None

    # ── Private ───────────────────────────────────────────────────────────

    def _search(self, query: str) -> tuple[list[dict[str, Any]], str | None]:
        if len(query.strip()) < 3:
            return [], "Search query too short."

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": SEARCH_RESULTS_COUNT,
            "include_answer": True,
            "include_raw_content": False,
            "include_images": False,
        }

        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            return [], "Search timed out."
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            return [], f"Tavily returned HTTP {code}."
        except requests.RequestException as exc:
            return [], f"Search request failed: {exc}"
        except ValueError:
            return [], "Tavily returned invalid JSON."

        results: list[dict[str, Any]] = []

        # Include the synthesized answer as the first source
        answer = data.get("answer")
        if answer:
            results.append({
                "title": "Tavily synthesized answer",
                "url": "",
                "content": str(answer),
            })

        for item in data.get("results", [])[:SEARCH_RESULTS_COUNT]:
            content = item.get("content") or item.get("snippet") or ""
            if not content:
                continue
            results.append({
                "title": item.get("title") or item.get("url") or "Untitled",
                "url": item.get("url", ""),
                "content": content,
            })

        return results, None
