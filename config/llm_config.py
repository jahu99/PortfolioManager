"""
LLM provider configuration.

Change these values to switch providers or control caching.
No command-line arguments are required.
"""

# ============================================================
# PROVIDER
# ============================================================

# Valid values:
#   "gemini"
#   "ollama"

LLM_PROVIDER = "gemini"


# ============================================================
# RESPONSE CACHE
# ============================================================

# True  = reuse identical previous LLM responses
# False = always call the configured provider

LLM_CACHE_ENABLED = True


# ============================================================
# CACHE LOCATION
# ============================================================

LLM_CACHE_PATH = "data/llm_review_cache.json"


# ============================================================
# GEMINI
# ============================================================

GEMINI_MODEL = "gemini-3.6-flash"


# ============================================================
# OLLAMA
# ============================================================

OLLAMA_MODEL = "qwen2.5:1.5b"
