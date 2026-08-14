# CompanyIntel Agent

An AI-powered Research & Recommendation Agent. Give it a company name; it researches
the company on the live web, reasons through its business situation in four
deliberate stages, and produces a structured intelligence report:

1. **Company Overview** — what they do, industry, scale, geography
2. **Key Business Information** — offerings, recent developments, expansion plans
3. **Potential Business Challenges** — operational, sales, and CX challenges, with reasoning
4. **AI Opportunities** — company-specific AI recommendations tied to the challenges above
5. **Personalized Pitch** — a one-page pitch as if addressing the company's CEO

Exportable as **Markdown, PDF, and Word (.docx)**.

Built to run at **zero cost**: every API used has a genuinely free tier, and no key is
mandatory to run the app (though one LLM key is required to actually generate reports).

---

## Quickstart

```bash
git clone <this repo> && cd company-intel-agent
chmod +x run.sh
./run.sh
```

`run.sh` creates a virtualenv, installs dependencies, copies `.env.example` → `.env`
if you don't have one, and launches the app at `http://localhost:8501`.

**Before your first real report**, open `.env` and add one free key:

| Provider | Free tier | Get a key |
|---|---|---|
| **Google Gemini** (default) | Generous free tier, no card required | https://aistudio.google.com/apikey |
| **Groq** (alternative, set `LLM_PROVIDER=groq`) | Free tier, very fast open-model inference | https://console.groq.com/keys |

Web research works out of the box with **no key at all** (free DuckDuckGo search).
Optionally add a `TAVILY_API_KEY` (https://tavily.com, free tier: 1,000 searches/month)
for higher-quality, agent-optimized search results.

### Manual setup (without run.sh)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your free API key
streamlit run app.py
```

---

## Try it

Use the example chips in the app, or type any company name:
`Adani Realty`, `Sobha`, `Prestige Group`, `Brigade Group`, `Puravankara`, or any other company.

A pre-generated example is included at `sample_outputs/Sobha_Limited_sample_report.md`
(and `.pdf` / `.docx`) so you can see the expected output shape without spending API quota.

---

## Project layout

```
company-intel-agent/
├── app.py                    # Streamlit UI (entrypoint)
├── config.py                 # env/config loading, provider selection
├── run.sh                    # one-shot setup + launch
├── requirements.txt
├── .env.example
├── agent/
│   ├── models.py              # report data schema (dataclasses)
│   ├── research.py            # web research (Tavily / DuckDuckGo fallback)
│   ├── llm_provider.py        # pluggable LLM layer (Gemini / Groq)
│   ├── synthesizer.py         # 4-stage reasoning pipeline (the "brain")
│   └── report_builder.py      # orchestrator + caching entrypoint
├── utils/
│   ├── cache.py                # disk cache to avoid burning free-tier quota
│   └── export.py               # Markdown / PDF / DOCX export
├── sample_outputs/             # pre-generated example report
├── tests/
│   └── test_agent.py           # mocked, zero-API-key smoke tests
└── DESIGN.md                   # architecture & documentation (approach,
                                 # challenges faced, how they were solved)
```

See **DESIGN.md** for the full write-up: approach, architecture diagram, AI tools used,
challenges faced during the build, and how they were solved.

## Tests

```bash
pip install pytest
pytest tests/ -v
```

All tests run with **zero API keys configured** — the LLM and search layers are mocked,
so the JSON-parsing, dataclass mapping, and export logic are verified independently of
any live API. This includes a headless UI regression test
(`tests/test_ui_click_flow.py`) that simulates real button clicks via Streamlit's
`AppTest` harness — it's what caught and proved the fix for a real reported bug
(see DESIGN.md, "Challenges Faced" #6).

