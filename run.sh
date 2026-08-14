#!/usr/bin/env bash
# CompanyIntel Agent — one-shot setup & launch script.
set -e

echo "== CompanyIntel Agent setup =="

# 1. Create venv if missing
if [ ! -d ".venv" ]; then
    echo "-> Creating virtual environment (.venv)"
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# 2. Install deps
echo "-> Installing dependencies"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# 3. Ensure .env exists
if [ ! -f ".env" ]; then
    echo "-> No .env found, copying .env.example -> .env"
    cp .env.example .env
    echo ""
    echo "!! Open .env and add a FREE API key before generating reports:"
    echo "   - GEMINI_API_KEY  (https://aistudio.google.com/apikey)"
    echo "   - or GROQ_API_KEY (https://console.groq.com/keys) with LLM_PROVIDER=groq"
    echo "   Optional: TAVILY_API_KEY for higher-quality search (https://tavily.com)"
    echo ""
fi

# 4. Launch
echo "-> Launching Streamlit app on http://localhost:8501"
streamlit run app.py
