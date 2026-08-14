# DESIGN.md — CompanyIntel Agent

## 1. Approach

The brief asks for five things: overview, key business info, challenges, AI
opportunities, and a personalized pitch — and explicitly warns against
generic answers. I treated that warning as the actual design constraint,
not the coding itself.

The failure mode I wanted to avoid: **one giant prompt** ("here's a company
name, give me all five sections") tends to produce plausible-sounding but
shallow output, because the model has to invent challenges and AI
recommendations without first grounding itself in real facts about the
company.

So the system is built around two ideas:

1. **Ground before reasoning.** Before any LLM call happens, the agent runs
   six targeted web searches (overview, offerings, recent news, expansion
   plans, customer sentiment, competitive position) and feeds the results
   in as context. The LLM is reasoning *about retrieved facts*, not from
   memory alone.
2. **Reason in stages, not one shot.** The report is built as a 4-stage
   pipeline where each stage consumes the previous stage's output (see
   Architecture below). This is the single biggest lever for output
   quality — it's what makes the AI Opportunities section map to *actual*
   challenges instead of a generic "use a chatbot!" list, and what makes
   the pitch reference specifics instead of boilerplate.

Everything was also built under one hard constraint I set for myself:
**genuinely $0 to run.** Every provider used (Gemini, Groq, Tavily,
DuckDuckGo) has a real free tier — not a trial that expires, not something
that needs a credit card. The app also runs and displays a helpful status
UI even with zero keys configured, and it never crashes, it just tells you
what's missing.

## 2. Architecture

### 2.1 High-level flow

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────────────────┐
│  Streamlit   │────▶│  report_builder   │────▶│   ReportSynthesizer        │
│  UI (app.py) │     │  (cache + entry)  │     │   (agent/synthesizer.py)   │
└─────────────┘     └──────────────────┘     └──────────────┬─────────────┘
                                                              │
                     ┌────────────────────────────────────────┴───────────────┐
                     ▼                                                        ▼
           ┌───────────────────┐                                  ┌────────────────────┐
           │   ResearchAgent    │                                  │      LLM Provider    │
           │ (agent/research.py)│                                  │ (agent/llm_provider) │
           │                    │                                  │                       │
           │ Tavily (free tier) │                                  │ Gemini (free tier)    │
           │  -- or if no key --│                                  │  -- or --             │
           │ DuckDuckGo (free,  │                                  │ Groq (free tier)      │
           │  no key needed)    │                                  │                       │
           └───────────────────┘                                  └────────────────────┘
```

### 2.2 The 4-stage reasoning pipeline (the core design decision)

```
 Stage 0            Stage 1                Stage 2             Stage 3                 Stage 4
 Research   ──▶   Overview +      ──▶    Challenges    ──▶   AI Opportunities   ──▶    CEO Pitch
 (6 queries)       Key Business Info      (grounded in         (grounded in            (grounded in
                   (grounded in           Stage 1)              Stage 1 + 2 —           Stages 1-3)
                   raw research)                                every opportunity
                                                                 either fixes a real
                                                                 challenge or exploits
                                                                 a real offering)
```

Each stage is a separate, purpose-built LLM call with its own prompt (see
`agent/synthesizer.py`). The `linked_challenge` field on every AI
Opportunity is enforced by the Stage 3 prompt, which is explicitly given
the Stage 2 challenge list and told to tie back to it — this is the
mechanism that prevents generic recommendations.

### 2.3 Provider abstraction

Both the LLM layer and the research layer are behind a small interface so
a new free provider can be added without touching the synthesizer:

- `agent/llm_provider.py` — `BaseLLM.generate(system, prompt)`. Implemented
  by `GeminiLLM` and `GroqLLM`. `generate_json()` wraps `generate()` and
  robustly extracts a JSON object even if the model wraps it in markdown
  fences or adds stray commentary.
- `agent/research.py` — `ResearchAgent._search()` dispatches to Tavily or
  DuckDuckGo based on whether `TAVILY_API_KEY` is set, entirely
  transparently to the rest of the app.

### 2.4 Data contract

`agent/models.py` defines the report as typed dataclasses
(`IntelligenceReport`, `CompanyOverview`, `KeyBusinessInfo`, `Challenge`,
`AIOpportunity`, `SourceRef`). Every downstream consumer — the Streamlit
UI, the Markdown/PDF/DOCX exporters, the cache, the tests — works against
this one contract instead of passing raw dicts around.

### 2.5 Caching

`utils/cache.py` is a minimal file-based cache keyed by `(company name,
day)`. Free-tier APIs have real rate limits, so re-running the same
company during a demo or during development doesn't re-spend quota. It's
intentionally simple — not meant to be a production cache layer.

## 3. AI tools used

| Purpose | Tool | Why |
|---|---|---|
| Reasoning / report synthesis | **Google Gemini** (`gemini-3.1-flash-lite`), free tier | Best free-tier reasoning quality available without a paid key; alternative Groq (`llama-3.3-70b-versatile`) provider included and swappable via one env var |
| Web research | **Tavily** (free tier, agent-oriented search API), with automatic fallback to **DuckDuckGo** (no key needed) | Tavily is purpose-built for grounding LLM agents; DuckDuckGo fallback guarantees the app works with literally zero configuration |
| Development | Claude (via Claude.ai), used throughout for architecture design, prompt engineering, and debugging the fpdf2 cursor-position bug (see below) | — |

I also used AI assistance (Claude) to help scaffold the boilerplate faster
and to reason through the prompt design for the 4-stage pipeline —
consistent with what the assessment explicitly encourages.

## 4. Challenges faced & how they were solved

**1. Generic-sounding output on the first pass.**
My first version used a single prompt asking for all 5 sections at once.
The AI Opportunities section kept coming back as boilerplate ("implement a
chatbot for customer service", "use AI for analytics") regardless of the
company. **Fix:** split into the 4-stage pipeline described above, and
explicitly required each AI Opportunity to reference either a specific
identified Challenge (`linked_challenge`) or a specific offering from the
Overview stage. This alone was the single biggest quality improvement in
the whole build.

**2. LLMs don't reliably return clean JSON.**
Even with an explicit "respond with ONLY JSON" instruction, models
occasionally wrap output in ```` ```json ```` fences or add a stray
sentence before/after. **Fix:** `BaseLLM._extract_json()` strips markdown
fences and, if `json.loads` still fails, regex-extracts the outermost
`{...}` block before parsing — so a slightly chatty response doesn't crash
the pipeline.

**3. fpdf2 cursor-position bug in PDF export.**
`multi_cell(0, h, text)` in fpdf2 leaves the text cursor at the **right**
margin instead of resetting to the left margin, so the very next
`multi_cell` call could raise `"Not enough horizontal space to render a
single character"`. This wasn't obvious from the error message. **Fix:**
every `multi_cell` call explicitly passes `new_x=XPos.LMARGIN,
new_y=YPos.NEXT`, wrapped in a small `cell()` helper so it's applied
consistently everywhere in `utils/export.py`. Caught by an automated test
(`test_pdf_export_produces_nonempty_bytes`) before it could reach a real
demo.

**4. Zero-cost constraint vs. output quality.**
Free-tier search and LLM APIs are noisier and more rate-limited than paid
ones. **Fix:** (a) multiple targeted search queries per company instead of
one broad query, to make the most of a limited free search budget; (b) the
day-scoped disk cache so repeated runs during development/demo don't churn
through quota; (c) retry logic with exponential backoff
(`tenacity`) on both the LLM and search calls to absorb transient free-tier
rate-limit errors gracefully instead of failing the whole report.

**5. Graceful degradation with no API keys.**
Since the deliverable needs to be runnable by someone else immediately,
the app needed to never hard-crash on missing configuration. **Fix:**
`config.py` centralizes all provider detection; the sidebar shows live
connection status; the "Generate" button is disabled with an explicit
inline explanation if no LLM key is present, instead of failing deep in
the pipeline.

**6. Streamlit widget state bug: clicking an example chip then Generate did nothing.**
The company-name input used `st.text_input(..., value=picked or
session_state.get("last_company",""))` with no explicit `key`. Clicking an
example chip correctly populated the box on that rerun, but on the
*following* rerun (triggered by clicking Generate), `picked` was `None`
again and `last_company` hadn't been set yet either — so the computed
`value` silently evaluated to `""` and the input reset to empty in the
same instant Generate fired. The button appeared to do nothing because
`generate_clicked and company_input.strip()` was `False`. **Fix:** the
input now uses a stable `key="company_name_input"` backed by
`st.session_state`, and example-chip clicks write directly into that
session_state key before the widget renders, instead of trying to compute
a `value=` each rerun. I wrote a headless regression test
(`tests/test_ui_click_flow.py`, using Streamlit's `AppTest` harness) that
simulates the exact click sequence and asserts the LLM actually gets
called and the report tabs render — it fails against the old code and
passes against the fix, which is the cleanest way I know to prove a UI
bug is actually fixed rather than "probably fixed."

**7. Gemini 2.0 Flash deprecation and 3.x "thinking token" truncation.**
Two real issues surfaced after initial delivery, both from Google's model
lineup moving under me between build and use. First, `gemini-2.0-flash`
(my original default) was deprecated and fully shut down by June 2026,
returning a `NotFound` error. **Fix:** defaulted to `gemini-3.1-flash-lite`,
a currently free-tier-eligible, stable model. Second, after that fix,
Stage 1 responses started getting cut off mid-JSON (visible in the terminal
log as `"industry": "` with no closing). Gemini's 3.x model family spends
part of the `max_output_tokens` budget on internal reasoning before writing
the visible answer, so my original 2048-token limit was silently being
consumed by thinking rather than the response. **Fix:** raised the budget
to 8192 across all four synthesis stages, and added an explicit
`finish_reason == MAX_TOKENS` check that raises a clear, actionable error
message instead of a generic JSON parse failure the next time output gets
truncated for any reason.

## 5. What I'd do with more time

- Add a second, independent verification pass that cross-checks factual
  claims in the Overview against the raw research context (a lightweight
  "grounding check") and flags any claim not traceable to a source.
- Add multi-company comparison mode (batch input, side-by-side report).
- Swap the file-based cache for a proper SQLite-backed store with TTL.
