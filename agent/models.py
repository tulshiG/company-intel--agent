"""
agent/models.py
----------------
Typed data structures for the intelligence report. Keeping these as
dataclasses (instead of passing raw dicts around) means every downstream
consumer (Streamlit UI, PDF export, tests) works against one contract.
"""
from dataclasses import dataclass, field, asdict
from typing import List
from datetime import datetime, timezone


@dataclass
class SourceRef:
    title: str
    url: str


@dataclass
class CompanyOverview:
    summary: str = ""
    industry: str = ""
    scale: str = ""
    geographic_presence: str = ""


@dataclass
class KeyBusinessInfo:
    major_offerings: List[str] = field(default_factory=list)
    recent_developments: List[str] = field(default_factory=list)
    expansion_plans: List[str] = field(default_factory=list)
    public_info_highlights: List[str] = field(default_factory=list)


@dataclass
class Challenge:
    title: str
    category: str          # operational | sales | customer_experience | other
    description: str
    reasoning: str          # WHY this is likely a challenge, grounded in research


@dataclass
class AIOpportunity:
    area: str               # automation | customer_engagement | sales | operations | analytics | document_processing
    title: str
    description: str        # company-specific, not generic
    expected_impact: str
    linked_challenge: str = ""  # ties back to a Challenge.title where relevant


@dataclass
class IntelligenceReport:
    company_name: str
    overview: CompanyOverview
    key_info: KeyBusinessInfo
    challenges: List[Challenge]
    ai_opportunities: List[AIOpportunity]
    pitch: str
    sources: List[SourceRef]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    llm_provider: str = ""
    search_backend: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
