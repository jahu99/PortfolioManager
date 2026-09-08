# ============================================================
# STOCK MOMENTUM AGENT
# LLM PROVIDER
# ============================================================

import json

import requests

from config.llm_config import (
    GEMINI_MODEL,
    LLM_PROVIDER,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OLLAMA_URL,
)


# ============================================================
# GEMINI
# ============================================================

def _call_gemini(prompt: str) -> str:
    """
    Send a prompt to Gemini and return the raw text response.
    """

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "Gemini provider requires the google-genai package. "
            "Install it with: pip install google-genai"
        ) from exc

    client = genai.Client()

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    if response is None:
        raise RuntimeError(
            "Gemini returned no response"
        )

    text = getattr(
        response,
        "text",
        None,
    )

    if not text:
        raise RuntimeError(
            "Gemini returned an empty response"
        )

    return str(text).strip()


# ============================================================
# OLLAMA
# ============================================================

def _call_ollama(prompt: str) -> str:
    """
    Send a prompt to Ollama and return the raw text response.
    """

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=OLLAMA_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    text = data.get(
        "response",
        "",
    )

    if not text:
        raise RuntimeError(
            "Ollama returned an empty response"
        )

    return str(text).strip()


# ============================================================
# PUBLIC PROVIDER INTERFACE
# ============================================================

def get_active_llm_provider() -> str:
    """
    Return the configured provider name.
    """

    provider = str(
        LLM_PROVIDER
    ).strip().lower()

    if provider not in {
        "gemini",
        "ollama",
    }:
        raise ValueError(
            "Unsupported LLM_PROVIDER: "
            f"{LLM_PROVIDER!r}. "
            "Supported values are 'gemini' and 'ollama'."
        )

    return provider


def get_active_model() -> str:
    """
    Return the configured model for the active provider.
    """

    provider = get_active_llm_provider()

    if provider == "gemini":
        return GEMINI_MODEL

    if provider == "ollama":
        return OLLAMA_MODEL

    raise RuntimeError(
        f"No model configured for provider: {provider}"
    )


def call_llm(prompt: str) -> str:
    """
    Call the configured LLM provider.

    Returns the raw text response.

    Provider selection is controlled exclusively by:

        config/llm_config.py
    """

    provider = get_active_llm_provider()

    print(
        f"LLM PROVIDER: {provider.upper()} | "
        f"MODEL: {get_active_model()}"
    )

    if provider == "gemini":
        return _call_gemini(prompt)

    if provider == "ollama":
        return _call_ollama(prompt)

    raise RuntimeError(
        f"Unsupported LLM provider: {provider}"
    )
