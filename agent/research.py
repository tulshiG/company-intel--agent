"""
agent/research.py
------------------
Gathers real-world, real-time context about a company before any LLM
reasoning happens. This grounds the report in actual facts instead of
letting the LLM hallucinate from parametric memory.

Provider selection (fully automatic, zero config needed for the free path):
    1. TAVILY_API_KEY set  -> Tavily search API (free tier: 1,000 req/month,
       purpose-built for AI agents, returns clean summarized snippets).
    2. No key              -> DuckDuckGo search (duckduckgo-search / ddgs
       package). Completely free, no API key, no signup required.

We fire several *targeted* queries (not one generic query) because the
assessment explicitly asks for overview, recent developments, expansion
plans, and public information — a single query returns a shallow mix of
all of these. Splitting the queries gives the synthesizer richer, more
specific grounding for each report section.
"""
from dataclasses import dataclass
from typing import List
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

from config import SETTINGS
from agent.models import SourceRef

logger = logging.getLogger(__name__)


@dataclass
class ResearchSnippet:
    query: str
    title: str
    url: str
    content: str


QUERY_TEMPLATES = [
    "{company} company overview business",
    "{company} products services offerings",
    "{company} recent news 2026",
    "{company} expansion plans upcoming projects",
    "{company} customer reviews complaints",
    "{company} competitors industry position",
]


class ResearchAgent:
    def __init__(self):
        self.backend = SETTINGS.search_backend
        if self.backend == "tavily":
            from tavily import TavilyClient
            self._client = TavilyClient(api_key=SETTINGS.tavily_api_key)
        else:
            self._client = None  # duckduckgo instantiated per-call (stateless)

    # -- public API -----------------------------------------------------
    def gather(self, company_name: str, max_results_per_query: int = 4) -> List[ResearchSnippet]:
        snippets: List[ResearchSnippet] = []
        failures = 0
        for template in QUERY_TEMPLATES:
            query = template.format(company=company_name)
            try:
                results = self._search(query, max_results_per_query)
                snippets.extend(results)
            except Exception as e:
                failures += 1
                logger.warning(f"Search failed for query '{query}': {e}")
        if failures == len(QUERY_TEMPLATES):
            logger.warning(
                "All web searches failed (backend=%s). Continuing with "
                "general-knowledge reasoning only \u2014 the report will note "
                "this and be less specific.", self.backend
            )
        return self._dedupe(snippets)

    # -- internals --------------------------------------------------------
    def _search(self, query: str, max_results: int) -> List[ResearchSnippet]:
        if self.backend == "tavily":
            return self._search_tavily_with_retry(query, max_results)
        # DuckDuckGo free search is prone to rate-limiting/blocking with no
        # useful error recovery from retrying immediately, so we try once
        # and fail fast rather than stalling the whole pipeline.
        return self._search_duckduckgo(query, max_results)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
    def _search_tavily_with_retry(self, query: str, max_results: int) -> List[ResearchSnippet]:
        return self._search_tavily(query, max_results)

    def _search_tavily(self, query: str, max_results: int) -> List[ResearchSnippet]:
        resp = self._client.search(query=query, max_results=max_results, search_depth="basic")
        out = []
        for r in resp.get("results", []):
            out.append(ResearchSnippet(
                query=query,
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", "")[:1200],
            ))
        return out

    def _search_duckduckgo(self, query: str, max_results: int) -> List[ResearchSnippet]:
        # Prefer the actively maintained `ddgs` package; fall back to the
        # old `duckduckgo_search` name if that's the only one installed.
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS  # legacy package name
        out = []
        with DDGS(timeout=8) as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                out.append(ResearchSnippet(
                    query=query,
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    content=(r.get("body", "") or "")[:1200],
                ))
        return out

    @staticmethod
    def _dedupe(snippets: List[ResearchSnippet]) -> List[ResearchSnippet]:
        seen = set()
        unique = []
        for s in snippets:
            key = s.url or s.title
            if key and key not in seen:
                seen.add(key)
                unique.append(s)
        return unique

    @staticmethod
    def to_context_block(snippets: List[ResearchSnippet]) -> str:
        """Flatten snippets into a single text block for LLM prompts."""
        lines = []
        for i, s in enumerate(snippets, 1):
            lines.append(f"[{i}] ({s.query}) {s.title}\nURL: {s.url}\n{s.content}\n")
        return "\n".join(lines)

    @staticmethod
    def to_source_refs(snippets: List[ResearchSnippet]) -> List[SourceRef]:
        return [SourceRef(title=s.title or s.url, url=s.url) for s in snippets if s.url]
