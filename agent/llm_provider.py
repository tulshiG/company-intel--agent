"""
agent/llm_provider.py
----------------------
Thin abstraction so the rest of the app doesn't care whether it's talking
to Gemini or Groq. Both are free-tier, API-key-based (NOT local/Ollama),
matching the requirement of "free but not a local model I have to host."

    - Gemini: generous free tier via Google AI Studio, good reasoning quality.
    - Groq:   free tier, extremely fast inference on open models (Llama 3.3).

Add a new provider by implementing `generate(system, prompt) -> str` and
registering it in `get_llm()`.
"""
import json
import re
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

from config import SETTINGS

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class BaseLLM:
    name = "base"

    def generate(self, system: str, prompt: str) -> str:
        raise NotImplementedError

    def generate_json(self, system: str, prompt: str) -> dict:
        """Call generate() and robustly parse a JSON object out of the reply,
        even if the model wraps it in markdown fences or adds stray text."""
        raw = self.generate(system, prompt)
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(raw: str) -> dict:
        text = raw.strip()
        text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text.strip()).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise LLMError(f"Could not parse JSON from LLM output:\n{raw[:500]}")


class GeminiLLM(BaseLLM):
    name = "gemini"

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=SETTINGS.gemini_api_key)
        self._genai = genai
        self._model_name = SETTINGS.gemini_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate(self, system: str, prompt: str) -> str:
        model = self._genai.GenerativeModel(self._model_name, system_instruction=system)
        # Gemini 3.x models spend part of max_output_tokens on internal
        # "thinking" before writing the visible answer, so a budget that
        # looks generous for the JSON alone can still get the response
        # truncated mid-output. 8192 leaves real headroom for both.
        resp = model.generate_content(
            prompt,
            generation_config={"temperature": 0.4, "max_output_tokens": 8192},
        )
        if not resp.candidates:
            raise LLMError("Gemini returned no candidates (possibly safety-blocked).")
        candidate = resp.candidates[0]
        finish_reason = getattr(candidate, "finish_reason", None)
        # finish_reason 2 == MAX_TOKENS in the Gemini API
        if finish_reason == 2 or str(finish_reason).upper().endswith("MAX_TOKENS"):
            raise LLMError(
                "Gemini cut its response off because it hit the output token "
                "limit (this happens with Gemini 3.x models, which spend part "
                "of the budget on internal reasoning before answering). Try "
                "again \u2014 this is usually transient \u2014 or lower "
                "GEMINI_MODEL to a lighter model in .env if it persists."
            )
        return resp.text


class GroqLLM(BaseLLM):
    name = "groq"

    def __init__(self):
        from groq import Groq
        self._client = Groq(api_key=SETTINGS.groq_api_key)
        self._model_name = SETTINGS.groq_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate(self, system: str, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model_name,
            temperature=0.4,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content


def get_llm() -> BaseLLM:
    if not SETTINGS.llm_configured:
        raise LLMError(
            "No LLM API key configured. Set GEMINI_API_KEY (or switch "
            "LLM_PROVIDER=groq and set GROQ_API_KEY) in your .env file. "
            "Both are free — see README.md for signup links."
        )
    if SETTINGS.llm_provider == "groq":
        return GroqLLM()
    return GeminiLLM()
