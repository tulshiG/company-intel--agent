"""
tests/test_agent.py
---------------------
Smoke tests that exercise the full pipeline WITHOUT hitting any real API
(everything is mocked), so `pytest` runs green with zero configured keys.
This verifies the JSON-parsing, dataclass-mapping, and export logic all
hold together end-to-end.

Run with:  pytest tests/ -v
"""
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.models import (
    IntelligenceReport, CompanyOverview, KeyBusinessInfo, Challenge,
    AIOpportunity, SourceRef,
)
from agent.llm_provider import BaseLLM
from utils import export


def _sample_report() -> IntelligenceReport:
    return IntelligenceReport(
        company_name="Acme Realty",
        overview=CompanyOverview(
            summary="Acme Realty is a mid-sized real estate developer focused on residential projects.",
            industry="Real Estate / Residential Development",
            scale="~500 employees, 15 active projects",
            geographic_presence="Bengaluru, Chennai",
        ),
        key_info=KeyBusinessInfo(
            major_offerings=["Residential apartments", "Villa communities"],
            recent_developments=["Launched new tower in Whitefield"],
            expansion_plans=["Entering Hyderabad market in 2027"],
            public_info_highlights=["Won 'Developer of the Year' 2025"],
        ),
        challenges=[
            Challenge(
                title="Slow post-sale query resolution",
                category="customer_experience",
                description="Buyers wait days for updates on documentation status.",
                reasoning="Multiple active projects across cities increase support load without a centralized system.",
            )
        ],
        ai_opportunities=[
            AIOpportunity(
                area="customer_engagement",
                title="Automated buyer query assistant",
                description="A WhatsApp-based assistant answering documentation/possession-date queries.",
                expected_impact="Reduced support load, faster buyer responses",
                linked_challenge="Slow post-sale query resolution",
            )
        ],
        pitch="Dear Leadership Team, ...",
        sources=[SourceRef(title="Acme Realty News", url="https://example.com/news")],
        llm_provider="gemini",
        search_backend="tavily",
    )


def test_extract_json_handles_markdown_fences():
    raw = '```json\n{"a": 1, "b": [2, 3]}\n```'
    parsed = BaseLLM._extract_json(raw)
    assert parsed == {"a": 1, "b": [2, 3]}


def test_extract_json_handles_stray_text():
    raw = 'Sure, here you go:\n{"a": 1}\nHope that helps!'
    parsed = BaseLLM._extract_json(raw)
    assert parsed == {"a": 1}


def test_markdown_export_contains_all_five_sections():
    report = _sample_report()
    md = export.to_markdown(report)
    for heading in [
        "1. Company Overview", "2. Key Business Information",
        "3. Potential Business Challenges", "4. AI Opportunities",
        "5. Personalized Pitch",
    ]:
        assert heading in md


def test_pdf_export_produces_nonempty_bytes():
    report = _sample_report()
    pdf_bytes = export.to_pdf_bytes(report)
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert len(pdf_bytes) > 500
    assert pdf_bytes[:4] == b"%PDF"


def test_docx_export_produces_nonempty_bytes():
    report = _sample_report()
    docx_bytes = export.to_docx_bytes(report)
    assert isinstance(docx_bytes, (bytes, bytearray))
    assert len(docx_bytes) > 500


@patch("agent.synthesizer.get_llm")
@patch("agent.synthesizer.ResearchAgent")
def test_synthesizer_full_pipeline_with_mocks(mock_research_agent_cls, mock_get_llm):
    """Exercises all 4 reasoning stages with a fully mocked LLM + search
    backend, proving the orchestration/JSON-mapping logic is correct
    independent of any live API."""
    from agent.synthesizer import ReportSynthesizer

    mock_research = MagicMock()
    mock_research.gather.return_value = []
    mock_research.to_context_block.return_value = ""
    mock_research.to_source_refs.return_value = []
    mock_research_agent_cls.return_value = mock_research

    mock_llm = MagicMock()
    mock_llm.name = "gemini"
    mock_llm.generate_json.side_effect = [
        {  # stage 1
            "overview": {"summary": "s", "industry": "i", "scale": "sc", "geographic_presence": "g"},
            "key_info": {"major_offerings": ["a"], "recent_developments": ["b"], "expansion_plans": ["c"], "public_info_highlights": ["d"]},
        },
        {"challenges": [{"title": "t", "category": "operational", "description": "d", "reasoning": "r"}]},  # stage 2
        {"opportunities": [{"area": "automation", "title": "t", "description": "d", "expected_impact": "e", "linked_challenge": "t"}]},  # stage 3
        {"pitch": "Dear CEO, ..."},  # stage 4
    ]
    mock_get_llm.return_value = mock_llm

    synth = ReportSynthesizer()
    report = synth.build_report("Acme Realty")

    assert report.company_name == "Acme Realty"
    assert report.overview.industry == "i"
    assert len(report.challenges) == 1
    assert len(report.ai_opportunities) == 1
    assert report.pitch == "Dear CEO, ..."
    assert mock_llm.generate_json.call_count == 4


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
