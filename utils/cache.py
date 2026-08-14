"""
utils/cache.py
----------------
Free-tier API keys have real rate/quota limits. This is a tiny file-based
cache keyed by (company name, day) so re-running a demo for the same
company doesn't burn quota or make the reviewer wait twice. Not meant to
be a production cache — just enough to make live demos smooth and cheap.
"""
import json
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


def _key(company_name: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = f"{company_name.strip().lower()}::{day}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def get(company_name: str) -> Optional[dict]:
    path = CACHE_DIR / f"{_key(company_name)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def set(company_name: str, report_dict: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{_key(company_name)}.json"
    path.write_text(json.dumps(report_dict, indent=2, default=str))


def clear() -> int:
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count
