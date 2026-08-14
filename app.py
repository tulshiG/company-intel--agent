"""
app.py
-------
CompanyIntel Agent — Streamlit front end.

Run with:  streamlit run app.py
"""
import logging
import streamlit as st

from config import SETTINGS
from agent.report_builder import generate_report
from agent.llm_provider import LLMError
from utils import export, cache

logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="CompanyIntel Agent",
    page_icon="\U0001F4CB",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Styling — "analyst briefing" aesthetic: near-black background, warm gold
# accent, a serif display face for headers (reads as a considered report,
# not a generic dashboard), monospace for metadata/system status.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

.dossier-title {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 2.4rem;
    color: #F0E6D2;
    letter-spacing: -0.5px;
    margin-bottom: 0;
}
.dossier-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: #D4A24C;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 2px;
}
.section-marker {
    font-family: 'JetBrains Mono', monospace;
    color: #D4A24C;
    font-size: 0.85rem;
    letter-spacing: 1px;
    border-bottom: 1px solid #2A313C;
    padding-bottom: 6px;
    margin-bottom: 10px;
}
.status-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    padding: 3px 10px;
    border-radius: 3px;
    display: inline-block;
    margin: 2px 4px 2px 0;
}
.status-ok { background: rgba(63,185,80,0.12); color: #3FB950; border: 1px solid rgba(63,185,80,0.35); }
.status-bad { background: rgba(229,83,75,0.12); color: #E5534B; border: 1px solid rgba(229,83,75,0.35); }
.challenge-card, .opp-card {
    background: #161B22;
    border-left: 3px solid #E5534B;
    border-radius: 4px;
    padding: 14px 18px;
    margin-bottom: 12px;
}
.opp-card { border-left-color: #3FB950; }
.card-title { font-family: 'Fraunces', serif; font-size: 1.1rem; color: #F0E6D2; }
.card-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: #9AA4AF;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.reasoning-block {
    font-size: 0.86rem;
    color: #9AA4AF;
    border-top: 1px dashed #2A313C;
    margin-top: 8px;
    padding-top: 8px;
}
.pitch-box {
    background: #161B22;
    border: 1px solid #2A313C;
    border-radius: 6px;
    padding: 28px 32px;
    font-size: 1.02rem;
    line-height: 1.75;
    white-space: pre-wrap;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar — system status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### System Status")

    llm_label = SETTINGS.llm_provider.upper()
    if SETTINGS.llm_configured:
        st.markdown(f'<span class="status-pill status-ok">LLM: {llm_label} \u2713 connected</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="status-pill status-bad">LLM: {llm_label} \u2717 no API key</span>', unsafe_allow_html=True)
        st.caption(
            "Add a free key to `.env`:\n\n"
            "- Gemini \u2014 aistudio.google.com/apikey\n"
            "- Groq \u2014 console.groq.com/keys"
        )

    backend_label = SETTINGS.search_backend.upper()
    st.markdown(f'<span class="status-pill status-ok">Search: {backend_label}</span>', unsafe_allow_html=True)
    # if SETTINGS.search_backend == "duckduckgo":
    #     st.caption("No Tavily key set \u2014 using free DuckDuckGo search (no key needed). Add TAVILY_API_KEY in `.env` for higher-quality results.")

    st.divider()
    st.markdown("### Options")
    force_refresh = st.checkbox("Force refresh (skip cache)", value=False)
    if st.button("Clear cached reports"):
        n = cache.clear()
        st.success(f"Cleared {n} cached report(s).")

    st.divider()
    st.caption("Built for the AI/ML Intern Assessment \u2014 Research & Recommendation Agent.")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<div class="dossier-title">CompanyIntel Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="dossier-sub">AI Research &amp; Recommendation Agent \u00b7 Public Sources Only</div>', unsafe_allow_html=True)
st.write("")
st.write(
    "Enter a company name to generate a structured intelligence report: overview, "
    "key business information, likely challenges, company-specific AI opportunities, "
    "and a personalized CEO pitch \u2014 grounded in live web research."
)

examples = ["Adani Realty", "Sobha", "Prestige Group", "Brigade Group", "Puravankara"]
st.caption("Try an example:")
cols = st.columns(len(examples))

if "company_name_input" not in st.session_state:
    st.session_state["company_name_input"] = ""

for col, name in zip(cols, examples):
    if col.button(name, use_container_width=True):
        # Set state BEFORE the widget below is instantiated this run, so
        # the text_input picks it up immediately via its key.
        st.session_state["company_name_input"] = name

company_input = st.text_input(
    "Company name",
    key="company_name_input",
    placeholder="e.g. Sobha Limited",
    label_visibility="collapsed",
)

generate_clicked = st.button("Generate Intelligence Report", type="primary", disabled=not SETTINGS.llm_configured)

if not SETTINGS.llm_configured:
    st.warning(
        "No LLM API key configured yet. Add a free `GEMINI_API_KEY` (or `GROQ_API_KEY`) "
        "to your `.env` file \u2014 see the sidebar for signup links \u2014 then restart the app."
    )

# ---------------------------------------------------------------------------
# Generate + render
# ---------------------------------------------------------------------------
if generate_clicked and company_input.strip():
    status_box = st.status("Starting research pipeline...", expanded=True)

    def on_progress(stage: str):
        status_box.update(label=stage)
        status_box.write(f"\u2192 {stage}")

    try:
        report = generate_report(company_input.strip(), progress_callback=on_progress, force_refresh=force_refresh)
        status_box.update(label="Report ready.", state="complete", expanded=False)
        st.session_state["report"] = report
    except LLMError as e:
        status_box.update(label="Failed.", state="error")
        st.error(str(e))
    except Exception as e:
        status_box.update(label="Failed.", state="error")
        st.error(f"Something went wrong while generating the report: {e}")

report = st.session_state.get("report")

if report:
    st.divider()

    dl_col1, dl_col2, dl_col3, _ = st.columns([1, 1, 1, 3])
    dl_col1.download_button(
        "\u2b07 Markdown", export.to_markdown(report),
        file_name=f"{report.company_name}_intelligence_report.md", mime="text/markdown",
        use_container_width=True,
    )
    dl_col2.download_button(
        "\u2b07 PDF", export.to_pdf_bytes(report),
        file_name=f"{report.company_name}_intelligence_report.pdf", mime="application/pdf",
        use_container_width=True,
    )
    dl_col3.download_button(
        "\u2b07 Word", export.to_docx_bytes(report),
        file_name=f"{report.company_name}_intelligence_report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )

    tabs = st.tabs(["01 \u00b7 Overview", "02 \u00b7 Key Info", "03 \u00b7 Challenges", "04 \u00b7 AI Opportunities", "05 \u00b7 Pitch", "Sources"])

    with tabs[0]:
        st.markdown('<div class="section-marker">COMPANY OVERVIEW</div>', unsafe_allow_html=True)
        st.write(report.overview.summary)
        c1, c2, c3 = st.columns(3)
        c1.metric("Industry", report.overview.industry or "\u2014")
        c2.metric("Scale", report.overview.scale or "\u2014")
        c3.metric("Geographic Presence", report.overview.geographic_presence or "\u2014")

    with tabs[1]:
        st.markdown('<div class="section-marker">KEY BUSINESS INFORMATION</div>', unsafe_allow_html=True)
        k1, k2 = st.columns(2)
        with k1:
            st.markdown("**Major Offerings**")
            for x in report.key_info.major_offerings:
                st.markdown(f"- {x}")
            st.markdown("**Recent Developments**")
            for x in report.key_info.recent_developments:
                st.markdown(f"- {x}")
        with k2:
            st.markdown("**Expansion Plans**")
            for x in report.key_info.expansion_plans:
                st.markdown(f"- {x}")
            st.markdown("**Other Public Info**")
            for x in report.key_info.public_info_highlights:
                st.markdown(f"- {x}")

    with tabs[2]:
        st.markdown('<div class="section-marker">POTENTIAL BUSINESS CHALLENGES</div>', unsafe_allow_html=True)
        for c in report.challenges:
            st.markdown(f"""
            <div class="challenge-card">
                <div class="card-tag">{c.category.replace('_',' ').upper()}</div>
                <div class="card-title">{c.title}</div>
                <div>{c.description}</div>
                <div class="reasoning-block"><b>Reasoning:</b> {c.reasoning}</div>
            </div>
            """, unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="section-marker">AI OPPORTUNITIES</div>', unsafe_allow_html=True)
        for o in report.ai_opportunities:
            linked = f"<div class='reasoning-block'>Addresses: <i>{o.linked_challenge}</i></div>" if o.linked_challenge else ""
            st.markdown(f"""
            <div class="opp-card">
                <div class="card-tag">{o.area.replace('_',' ').upper()}</div>
                <div class="card-title">{o.title}</div>
                <div>{o.description}</div>
                <div class="reasoning-block"><b>Expected impact:</b> {o.expected_impact}</div>
                {linked}
            </div>
            """, unsafe_allow_html=True)

    with tabs[4]:
        st.markdown('<div class="section-marker">PERSONALIZED PITCH</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pitch-box">{report.pitch}</div>', unsafe_allow_html=True)

    with tabs[5]:
        st.markdown('<div class="section-marker">RESEARCH SOURCES</div>', unsafe_allow_html=True)
        if report.sources:
            for s in report.sources:
                st.markdown(f"- [{s.title or s.url}]({s.url})")
        else:
            st.caption("No source URLs were captured for this report.")

    st.caption(
        f"Generated {report.generated_at} UTC \u00b7 LLM: {report.llm_provider} \u00b7 "
        f"Search: {report.search_backend} \u00b7 {len(report.sources)} sources"
    )
