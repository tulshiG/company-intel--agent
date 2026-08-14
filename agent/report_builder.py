"""
agent/report_builder.py
--------------------------
Public entrypoint used by the Streamlit UI. Wraps the synthesizer with the
disk cache so re-generating a report for the same company on the same day
doesn't re-spend free-tier API quota.
"""
from dataclasses import asdict
import logging

from agent.models import (
    IntelligenceReport, CompanyOverview, KeyBusinessInfo, Challenge,
    AIOpportunity, SourceRef,
)
from agent.synthesizer import ReportSynthesizer
from config import SETTINGS
from utils import cache

logger = logging.getLogger(__name__)


def generate_report(company_name: str, progress_callback=None, force_refresh: bool = False) -> IntelligenceReport:
    company_name = company_name.strip()
    if not company_name:
        raise ValueError("Company name cannot be empty.")

    if SETTINGS.enable_cache and not force_refresh:
        cached = cache.get(company_name)
        if cached:
            if progress_callback:
                progress_callback("Loaded from cache (same company, same day) \u2014 no API calls used.")
            return _dict_to_report(cached)

    synthesizer = ReportSynthesizer(progress_callback=progress_callback)
    report = synthesizer.build_report(company_name)

    if SETTINGS.enable_cache:
        cache.set(company_name, report.to_dict())

    return report


def _dict_to_report(d: dict) -> IntelligenceReport:
    return IntelligenceReport(
        company_name=d["company_name"],
        overview=CompanyOverview(**d["overview"]),
        key_info=KeyBusinessInfo(**d["key_info"]),
        challenges=[Challenge(**c) for c in d["challenges"]],
        ai_opportunities=[AIOpportunity(**o) for o in d["ai_opportunities"]],
        pitch=d["pitch"],
        sources=[SourceRef(**s) for s in d["sources"]],
        generated_at=d.get("generated_at", ""),
        llm_provider=d.get("llm_provider", ""),
        search_backend=d.get("search_backend", ""),
    )
