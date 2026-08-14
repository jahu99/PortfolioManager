"""
AI engine for local Ollama/Llama analysis.

This module is the single boundary between the application and Ollama.
Successful Llama responses are cached by request content so repeated
analysis requests do not unnecessarily invoke the local LLM.

The cache is deliberately limited to the actual Llama response layer.
Stock scoring, ranking, portfolio decisions and the Top-N AI selection
remain controlled by the existing application logic.
"""

import hashlib
import json
import traceback
from pathlib import Path

import ollama


# ---------------------------------
# Ollama Model Configuration
# ---------------------------------

MODEL = "llama3.1:latest"

TEMPERATURE = 0.2
NUM_PREDICT = 300
TOP_P = 0.9


# ---------------------------------
# AI Cache Configuration
# ---------------------------------

AI_CACHE_DIR = Path("data/cache/ai")


def _build_cache_key(prompt):
    """
    Build a deterministic cache key for an Ollama request.

    The key includes the model, prompt and generation parameters so that
    changing any material part of the request results in a new cache entry.
    """

    cache_payload = {
        "model": MODEL,
        "prompt": prompt,
        "temperature": TEMPERATURE,
        "num_predict": NUM_PREDICT,
        "top_p": TOP_P,
    }

    payload = json.dumps(
        cache_payload,
        sort_keys=True,
        ensure_ascii=False,
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def _get_cache_path(prompt):
    """
    Return the cache file path for an Ollama request.
    """

    cache_key = _build_cache_key(prompt)

    return AI_CACHE_DIR / f"{cache_key}.json"


def _load_cached_response(prompt):
    """
    Load a previously generated Llama response.

    Returns:
        str | None
    """

    cache_path = _get_cache_path(prompt)

    if not cache_path.exists():
        return None

    try:

        with cache_path.open(
            "r",
            encoding="utf-8",
        ) as f:

            cached = json.load(f)

        response = cached.get(
            "response"
        )

        if response:

            print(
                "OLLAMA CACHE HIT:",
                cache_path.name
            )

            return response

    except Exception as e:

        print(
            f"AI CACHE READ ERROR: {e}"
        )

    return None


def _save_cached_response(prompt, response):
    """
    Persist a successful Llama response to the local cache.
    """

    try:

        AI_CACHE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        cache_path = _get_cache_path(prompt)

        payload = {
            "model": MODEL,
            "response": response,
        }

        with cache_path.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(
            "OLLAMA RESPONSE CACHED:",
            cache_path.name
        )

    except Exception as e:

        # Cache failure must never break the AI analysis.
        print(
            f"AI CACHE WRITE ERROR: {e}"
        )


# ---------------------------------
# AI Response Generator
# ---------------------------------

def generate_ai_response(prompt):
    """
    Generate a response using the local Ollama/Llama model.

    A successful response is cached using a deterministic hash of the
    complete request. Repeated identical requests therefore avoid another
    Ollama invocation.

    The caller remains responsible for deciding which stocks should receive
    AI analysis. In the main application this is controlled by
    AI_ANALYSIS_LIMIT.
    """

    # ---------------------------------
    # Cache lookup
    # ---------------------------------

    cached_response = _load_cached_response(
        prompt
    )

    if cached_response is not None:

        return cached_response


    # ---------------------------------
    # Llama generation
    # ---------------------------------

    try:

        print(
            "OLLAMA CALL STARTED"
        )

        response = ollama.chat(

            model=MODEL,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            options={

                "temperature":
                    TEMPERATURE,

                "num_predict":
                    NUM_PREDICT,

                "top_p":
                    TOP_P

            }

        )


        print(
            "OLLAMA RESPONSE RECEIVED"
        )


        content = response[
            "message"
        ][
            "content"
        ]


        # ---------------------------------
        # Cache successful response
        # ---------------------------------

        if content:

            _save_cached_response(
                prompt,
                content
            )


        return content


    except KeyboardInterrupt:

        print(
            "AI generation interrupted"
        )

        return (
            "AI analysis unavailable - generation interrupted"
        )


    except Exception as e:

        print(
            f"AI ENGINE ERROR: {e}"
        )

        traceback.print_exc()

        return (
            "AI analysis unavailable"
        )


# ---------------------------------
# Health Check
# ---------------------------------

def test_ai_engine():

    try:

        print(
            "Testing Ollama model:",
            MODEL
        )


        response = ollama.chat(

            model=MODEL,

            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly: AI OK"
                }
            ],

            options={

                "temperature":
                    TEMPERATURE,

                "num_predict":
                    10

            }

        )


        return response[
            "message"
        ][
            "content"
        ]


    except Exception as e:

        return (
            f"AI engine unavailable: {e}"
        )


# ---------------------------------
# Main Test
# ---------------------------------

if __name__ == "__main__":

    print(
        test_ai_engine()
    )