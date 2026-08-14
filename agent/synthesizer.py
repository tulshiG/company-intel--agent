"""
agent/synthesizer.py
----------------------
This is the reasoning core of the agent. Instead of one giant prompt that
asks for everything at once (which tends to produce shallow, generic
output), the report is built in FOUR deliberate stages, each grounded in
the outputs of the one before it:

    Stage 1  Overview + Key Business Info   <- grounded in raw research
    Stage 2  Challenges                     <- grounded in Stage 1 output
    Stage 3  AI Opportunities               <- grounded in Stage 1 + Stage 2
                                                (so opportunities map to REAL
                                                 challenges/offerings, not
                                                 generic "use AI!" filler)
    Stage 4  CEO Pitch                      <- grounded in Stages 1-3

This mirrors how a human analyst would actually work: understand the
business, THEN reason about its pain points, THEN propose fixes, THEN
pitch. It's slower than one shot but produces much more defensible,
company-specific output — which is what the assessment is scored on.
"""
from typing import List
import logging

from agent.models import (
    CompanyOverview, KeyBusinessInfo, Challenge, AIOpportunity,
    IntelligenceReport, SourceRef,
)
from agent.research import ResearchAgent
from agent.llm_provider import get_llm
from config import SETTINGS

logger = logging.getLogger(__name__)

BASE_SYSTEM = (
    "You are a senior business intelligence analyst preparing a report for "
    "an AI solutions company that is about to pitch to this target company. "
    "You are precise, specific, and never generic. You ground every claim in "
    "the provided research context. If the research doesn't cover something, "
    "you reason carefully from the industry and business model instead of "
    "inventing facts. You always respond with ONLY a single valid JSON object "
    "matching the schema given — no markdown fences, no commentary."
)


class ReportSynthesizer:
    def __init__(self, progress_callback=None):
        """progress_callback(stage: str) is called before each stage, so the
        UI can show live progress."""
        self.llm = get_llm()
        self.research_agent = ResearchAgent()
        self._progress = progress_callback or (lambda stage: None)

    def build_report(self, company_name: str) -> IntelligenceReport:
        self._progress("Researching company across the web...")
        snippets = self.research_agent.gather(company_name)
        context = self.research_agent.to_context_block(snippets)
        sources = self.research_agent.to_source_refs(snippets)
        if snippets:
            self._progress(f"Found {len(snippets)} web sources. Analyzing...")
        else:
            self._progress("No web sources retrieved (search may be rate-limited) \u2014 continuing with general reasoning...")

        self._progress("Analyzing company overview & key business info...")
        overview, key_info = self._stage1_overview(company_name, context)

        self._progress("Reasoning through business challenges...")
        challenges = self._stage2_challenges(company_name, overview, key_info, context)

        self._progress("Identifying company-specific AI opportunities...")
        opportunities = self._stage3_ai_opportunities(company_name, overview, key_info, challenges)

        self._progress("Drafting personalized CEO pitch...")
        pitch = self._stage4_pitch(company_name, overview, challenges, opportunities)

        return IntelligenceReport(
            company_name=company_name,
            overview=overview,
            key_info=key_info,
            challenges=challenges,
            ai_opportunities=opportunities,
            pitch=pitch,
            sources=sources,
            llm_provider=self.llm.name,
            search_backend=SETTINGS.search_backend,
        )

    # ---- Stage 1: Overview + Key Info ----------------------------------
    def _stage1_overview(self, company: str, context: str):
        prompt = f"""Company: {company}

RESEARCH CONTEXT (web search results, may be incomplete or noisy):
{context if context.strip() else "(No web results were retrieved. Reason from general industry knowledge and clearly keep claims high-level.)"}

Using only the context above (plus careful general reasoning where context is thin),
produce a JSON object with this exact schema:

{{
  "overview": {{
    "summary": "2-4 sentence factual summary of what the company does",
    "industry": "specific industry/sub-sector",
    "scale": "size indicators: revenue, employee count, project count, market cap etc. if known, else best estimate framed as such",
    "geographic_presence": "cities/states/countries of operation"
  }},
  "key_info": {{
    "major_offerings": ["3-6 specific products/services/business lines"],
    "recent_developments": ["2-5 specific recent news items, launches, or announcements"],
    "expansion_plans": ["1-4 specific expansion or growth plans, or 'None found in available sources' if truly none"],
    "public_info_highlights": ["2-4 other notable public facts: partnerships, awards, leadership, financials"]
  }}
}}

Be specific and concrete. Do not use vague filler like "the company is doing well".
Respond with ONLY the JSON object."""
        data = self.llm.generate_json(BASE_SYSTEM, prompt)
        ov = data.get("overview", {})
        ki = data.get("key_info", {})
        overview = CompanyOverview(
            summary=ov.get("summary", ""),
            industry=ov.get("industry", ""),
            scale=ov.get("scale", ""),
            geographic_presence=ov.get("geographic_presence", ""),
        )
        key_info = KeyBusinessInfo(
            major_offerings=ki.get("major_offerings", []),
            recent_developments=ki.get("recent_developments", []),
            expansion_plans=ki.get("expansion_plans", []),
            public_info_highlights=ki.get("public_info_highlights", []),
        )
        return overview, key_info

    # ---- Stage 2: Challenges --------------------------------------------
    def _stage2_challenges(self, company: str, overview: CompanyOverview,
                            key_info: KeyBusinessInfo, context: str) -> List[Challenge]:
        prompt = f"""Company: {company}

CONFIRMED OVERVIEW:
{overview}

KEY BUSINESS INFO:
{key_info}

ADDITIONAL RAW RESEARCH CONTEXT:
{context[:4000]}

Think like an operations + sales + CX consultant. Identify the most PLAUSIBLE
real business challenges this specific company faces right now, reasoning
from its industry, scale, offerings, and geography — not generic industry
cliches. Cover a spread across these categories where plausible: operational
bottlenecks, sales challenges, customer experience challenges, and one
"other" strategic challenge if relevant.

Return JSON:
{{
  "challenges": [
    {{
      "title": "short challenge name",
      "category": "operational | sales | customer_experience | other",
      "description": "what the challenge concretely looks like for THIS company",
      "reasoning": "why you believe this, tied to specific facts from the overview/context above (scale, geography, offerings, recent developments)"
    }}
  ]
}}

Produce 4-6 challenges. Every "reasoning" field must reference a specific
fact about this company, not a generic industry statement. Respond with
ONLY the JSON object."""
        data = self.llm.generate_json(BASE_SYSTEM, prompt)
        return [Challenge(**c) for c in data.get("challenges", [])]

    # ---- Stage 3: AI Opportunities ----------------------------------------
    def _stage3_ai_opportunities(self, company: str, overview: CompanyOverview,
                                  key_info: KeyBusinessInfo,
                                  challenges: List[Challenge]) -> List[AIOpportunity]:
        challenges_text = "\n".join(
            f"- [{c.category}] {c.title}: {c.description}" for c in challenges
        )
        prompt = f"""Company: {company}

OVERVIEW: {overview}
OFFERINGS: {key_info.major_offerings}

IDENTIFIED CHALLENGES:
{challenges_text}

Now propose AI solutions SPECIFIC to this company. Each opportunity must
either directly address one of the challenges above (set "linked_challenge"
to that challenge's title) or exploit a specific offering/process mentioned
in the overview. Do NOT propose generic solutions like "use a chatbot" or
"use AI for analytics" without tying it to this company's actual business
(e.g. name what data, what workflow, what team it affects, given what you
know about this specific company and its industry).

Cover a spread across areas where genuinely applicable: automation,
customer engagement, sales, operations, analytics, document processing.

Return JSON:
{{
  "opportunities": [
    {{
      "area": "automation | customer_engagement | sales | operations | analytics | document_processing",
      "title": "short solution name",
      "description": "specific description of what it does for THIS company and how it plugs into their actual process",
      "expected_impact": "concrete expected business impact (efficiency, revenue, retention, cost) — qualitative estimate is fine, don't fabricate precise numbers",
      "linked_challenge": "title of the challenge this solves, or '' if it's offering-driven instead"
    }}
  ]
}}

Produce 4-6 opportunities. Respond with ONLY the JSON object."""
        data = self.llm.generate_json(BASE_SYSTEM, prompt)
        return [AIOpportunity(**o) for o in data.get("opportunities", [])]

    # ---- Stage 4: CEO Pitch -----------------------------------------------
    def _stage4_pitch(self, company: str, overview: CompanyOverview,
                       challenges: List[Challenge],
                       opportunities: List[AIOpportunity]) -> str:
        top_challenges = "\n".join(f"- {c.title}: {c.description}" for c in challenges[:3])
        top_opps = "\n".join(
            f"- {o.title} ({o.area}): {o.description} -> {o.expected_impact}"
            for o in opportunities[:4]
        )
        prompt = f"""Company: {company}
Overview: {overview.summary}

TOP CHALLENGES IDENTIFIED:
{top_challenges}

RECOMMENDED AI SOLUTIONS:
{top_opps}

Write a one-page personalized pitch as if you are about to meet the CEO of
{company}. Structure it in flowing prose (not bullet-dump) covering:
1. Why you reached out — reference something SPECIFIC and real about their
   business (a recent development, scale, or market position), not a
   generic opener.
2. The 2-3 opportunities/challenges you noticed, stated confidently but
   respectfully (you're an outsider offering perspective, not lecturing).
3. The AI solutions you'd recommend and the tangible outcome each would
   drive for THEM specifically.
4. A warm, low-pressure call to action (e.g. propose a short working
   session, not a hard sell).

Tone: confident, consultative, concise. Roughly 350-450 words. Address the
CEO directly ("Dear [CEO name or 'Leadership Team' if unknown]," style open).

Return JSON: {{"pitch": "full pitch text here"}}
Respond with ONLY the JSON object."""
        data = self.llm.generate_json(BASE_SYSTEM, prompt)
        return data.get("pitch", "")
