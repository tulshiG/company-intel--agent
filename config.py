"""
config.py
---------
Single source of truth for environment / provider configuration.
Everything here is designed so the app degrades gracefully:
  - No Tavily key?  -> fall back to free DuckDuckGo search.
  - No LLM key set? -> app tells the user clearly in the UI instead of crashing.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

    # Research
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "").strip()

    # Misc
    enable_cache: bool = os.getenv("ENABLE_CACHE", "true").strip().lower() == "true"

    @property
    def active_llm_key(self) -> str:
        return self.gemini_api_key if self.llm_provider == "gemini" else self.groq_api_key

    @property
    def llm_configured(self) -> bool:
        return bool(self.active_llm_key)

    @property
    def search_backend(self) -> str:
        return "tavily" if self.tavily_api_key else "duckduckgo"


SETTINGS = Settings()
