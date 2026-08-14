"""
tests/test_ui_click_flow.py
------------------------------
Regression test for a real bug reported by a user: clicking an example
company chip and then clicking "Generate Intelligence Report" silently
did nothing (the page appeared to just "refresh"). Root cause: the
company-name text_input used a recomputed `value=` each rerun instead of
a stable `key=`-backed session_state entry, so the input silently reset
to empty on the very rerun that Generate was clicked.

This runs as a genuine subprocess (not sharing Python state with the rest
of the test suite) via `pytest -s`, using Streamlit's AppTest harness to
simulate real clicks with the LLM and search layers mocked out.
"""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "_ui_click_flow_check.py"


def test_example_chip_then_generate_flow():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=60,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
    assert result.returncode == 0, (
        "UI click-flow regression check failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
