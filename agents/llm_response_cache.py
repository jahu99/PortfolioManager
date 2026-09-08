# ============================================================
# STOCK MOMENTUM AGENT
# LLM RESPONSE CACHE
# ============================================================

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config.llm_config import (
    LLM_CACHE_ENABLED,
    LLM_CACHE_TTL_HOURS,
)

from agents.llm_provider import (
    get_active_llm_provider,
    get_active_model,
)


# ============================================================
# DATABASE LOCATION
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent.parent

DATABASE_PATH = (
    PROJECT_ROOT
    / "portfolio_manager.db"
)


# ============================================================
# CACHE TABLE
# ============================================================

def initialise_llm_cache() -> None:
    """
    Create the LLM response cache table if required.
    """

    with sqlite3.connect(
        DATABASE_PATH
    ) as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_response_cache (
                cache_key TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_llm_response_cache_created_at
            ON llm_response_cache(created_at)
            """
        )


# ============================================================
# CACHE KEY
# ============================================================

def build_cache_key(
    prompt: str,
) -> str:
    """
    Build a provider/model-specific deterministic cache key.

    Gemini and Ollama must never share cached responses.
    """

    provider = get_active_llm_provider()
    model = get_active_model()

    payload = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
    }

    serialised = json.dumps(
        payload,
        sort_keys=True,
        default=str,
    )

    return hashlib.sha256(
        serialised.encode("utf-8")
    ).hexdigest()


# ============================================================
# READ CACHE
# ============================================================

def get_cached_response(
    prompt: str,
) -> Optional[str]:
    """
    Return a valid cached response.

    Returns None when:

    - caching is disabled
    - no matching response exists
    - the cached response has expired
    """

    if not LLM_CACHE_ENABLED:
        print(
            "LLM CACHE: DISABLED"
        )
        return None

    initialise_llm_cache()

    cache_key = build_cache_key(
        prompt
    )

    expiry = (
        datetime.utcnow()
        - timedelta(
            hours=LLM_CACHE_TTL_HOURS
        )
    )

    with sqlite3.connect(
        DATABASE_PATH
    ) as connection:

        row = connection.execute(
            """
            SELECT
                response,
                created_at
            FROM llm_response_cache
            WHERE cache_key = ?
            """,
            (
                cache_key,
            ),
        ).fetchone()

    if row is None:

        print(
            "LLM CACHE: MISS"
        )

        return None

    response, created_at = row

    try:

        cached_at = datetime.fromisoformat(
            created_at
        )

    except ValueError:

        print(
            "LLM CACHE: INVALID TIMESTAMP"
        )

        return None

    if cached_at < expiry:

        print(
            "LLM CACHE: EXPIRED"
        )

        return None

    print(
        "LLM CACHE: HIT"
    )

    return response


# ============================================================
# WRITE CACHE
# ============================================================

def save_cached_response(
    prompt: str,
    response: str,
) -> None:
    """
    Save an LLM response.

    Does nothing when caching is disabled.
    """

    if not LLM_CACHE_ENABLED:
        return

    initialise_llm_cache()

    cache_key = build_cache_key(
        prompt
    )

    provider = get_active_llm_provider()
    model = get_active_model()

    prompt_hash = hashlib.sha256(
        prompt.encode("utf-8")
    ).hexdigest()

    created_at = datetime.utcnow().isoformat()

    with sqlite3.connect(
        DATABASE_PATH
    ) as connection:

        connection.execute(
            """
            INSERT OR REPLACE INTO
            llm_response_cache (
                cache_key,
                provider,
                model,
                prompt_hash,
                response,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                provider,
                model,
                prompt_hash,
                response,
                created_at,
            ),
        )

    print(
        "LLM CACHE: SAVED"
    )


# ============================================================
# CACHE MANAGEMENT
# ============================================================

def clear_llm_cache() -> None:
    """
    Delete all cached LLM responses.
    """

    initialise_llm_cache()

    with sqlite3.connect(
        DATABASE_PATH
    ) as connection:

        connection.execute(
            """
            DELETE FROM llm_response_cache
            """
        )

    print(
        "LLM CACHE: CLEARED"
    )
