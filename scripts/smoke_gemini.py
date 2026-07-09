"""Smoke test Gemini via repo AI handler. Prints OK/FAIL only."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import get_settings
from backend.core.llm_capabilities import effective_cloud_api_key
from backend.core.llm_gateway import llm_complete

get_settings.cache_clear()
s = get_settings()
print(f"ollama_enabled={s.ollama_enabled} cloud_key={'yes' if effective_cloud_api_key() else 'no'}")

result = llm_complete("Reply with exactly: GEMINI_OK", task="notes_chunk", tier="medium", timeout=90)
if result.text and "GEMINI_OK" in result.text.upper():
    print(f"OK provider={result.provider} model={result.model}")
elif result.text:
    print(f"OK_PARTIAL provider={result.provider} model={result.model} len={len(result.text)}")
else:
    print(f"FAIL error={result.error} provider={result.provider} model={result.model}")
    for a in result.attempts or []:
        print(f"  attempt {a.get('provider')}:{a.get('model')} err={a.get('error')}")
    sys.exit(1)
