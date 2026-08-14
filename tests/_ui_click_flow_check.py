"""
tests/_ui_click_flow_check.py
--------------------------------
Standalone script (run as a subprocess by test_ui_click_flow.py for full
process isolation). Simulates: click "Adani Realty" example chip, then
click "Generate Intelligence Report" -- the exact sequence reported as
broken -- using Streamlit's AppTest harness with the LLM/search layers
mocked out.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["GEMINI_API_KEY"] = "dummy-key-for-ui-test"
os.environ["ENABLE_CACHE"] = "false"

from streamlit.testing.v1 import AppTest  # noqa: E402

stage1 = {
    "overview": {"summary": "Adani Realty is a real estate arm of the Adani Group.",
                 "industry": "Real Estate", "scale": "Large", "geographic_presence": "India"},
    "key_info": {"major_offerings": ["Residential", "Commercial"], "recent_developments": ["Launch X"],
                 "expansion_plans": ["City Y"], "public_info_highlights": ["Part of Adani Group"]},
}
stage2 = {"challenges": [{"title": "T", "category": "operational", "description": "d", "reasoning": "r"}]}
stage3 = {"opportunities": [{"area": "automation", "title": "T", "description": "d", "expected_impact": "e", "linked_challenge": "T"}]}
stage4 = {"pitch": "Dear CEO, ..."}

mock_llm = MagicMock()
mock_llm.name = "gemini"
mock_llm.generate_json.side_effect = [stage1, stage2, stage3, stage4] * 5

mock_research = MagicMock()
mock_research.gather.return_value = []
mock_research.to_context_block.return_value = ""
mock_research.to_source_refs.return_value = []

with patch("agent.synthesizer.get_llm", return_value=mock_llm), \
     patch("agent.synthesizer.ResearchAgent", return_value=mock_research):

    at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
    at.run()
    assert not at.exception, f"Initial load raised: {at.exception}"
    print("STEP 1 OK: app loaded, no exception")

    example_button = next(b for b in at.button if b.label == "Adani Realty")
    example_button.click().run()
    assert not at.exception, f"After clicking example chip: {at.exception}"

    text_input_value = at.text_input(key="company_name_input").value
    print(f"STEP 2 OK: after clicking 'Adani Realty' chip, text_input value = {text_input_value!r}")
    assert text_input_value == "Adani Realty", "BUG: text input did not pick up the example click!"

    # Now click Generate -- this is the exact second step the user reported as broken
    generate_button = next(b for b in at.button if b.label == "Generate Intelligence Report")
    generate_button.click().run()
    assert not at.exception, f"After clicking Generate: {at.exception}"

    text_input_value_after = at.text_input(key="company_name_input").value
    print(f"STEP 3 OK: text_input value right before generation = {text_input_value_after!r}")
    assert text_input_value_after == "Adani Realty", "BUG: input reset to empty before generate ran!"

    assert mock_llm.generate_json.call_count >= 4, "LLM was never actually called -- report was not generated!"
    print(f"STEP 4 OK: LLM was called {mock_llm.generate_json.call_count} times (report generation ran)")

    tab_labels = [t.label for t in at.tabs]
    print(f"STEP 5: rendered tabs = {tab_labels}")
    assert any("Overview" in t for t in tab_labels), "BUG: report tabs did not render on screen!"

    print("\nALL CHECKS PASSED -- example chip -> Generate flow now works end-to-end.")
