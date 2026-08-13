"""The one place a language model is called.

Kept behind a tiny interface so the rest of the pipeline can be tested without a key, and
so swapping providers touches one file. No API key ships with this repo — whoever runs it
supplies their own.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

try:                                   # optional: the app works with real env vars too
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


class Asker(Protocol):
    def __call__(self, system: str, text: str) -> str: ...


def anthropic_asker(model: str | None = None, key: str | None = None) -> Asker:
    """Real model calls. Raises at construction if no key is configured."""
    import anthropic

    key = key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Create a key at console.anthropic.com and put "
            "it in a .env file at the project root. Everything except the model call runs "
            "without one."
        )

    client = anthropic.Anthropic(api_key=key)
    model = model or os.environ.get("EXTRACTION_MODEL", "claude-haiku-4-5-20251001")

    def ask(system: str, text: str) -> str:
        response = client.messages.create(
            model=model,
            max_tokens=100,                       # a name, nothing more
            system=[{
                "type": "text",
                "text": system,
                # The instructions are identical on every call and are most of the prompt.
                # Caching them means we pay for the document, not the schema.
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": text}],
        )
        return response.content[0].text.strip() if response.content else ""

    return ask


def openai_asker(model: str | None = None, key: str | None = None) -> Asker:
    """OpenAI equivalent. Raises at construction if no key is configured."""
    from openai import OpenAI

    key = key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Create a key at platform.openai.com/api-keys and "
            "put it in a .env file at the project root."
        )

    client = OpenAI(api_key=key)
    model = model or os.environ.get("EXTRACTION_MODEL", "gpt-4o-mini")

    def ask(system: str, text: str) -> str:
        response = client.chat.completions.create(
            model=model,
            max_tokens=100,                       # a name, nothing more
            temperature=0,                        # same document, same answer
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": text}],
        )
        return (response.choices[0].message.content or "").strip()

    return ask


def echo_asker(answers: dict[str, str] | None = None, default: str = "NOT_FOUND") -> Asker:
    """Offline stand-in. Returns the first line of the text that looks like a name, so the
    pipeline can be exercised end to end without a key or a bill."""
    answers = answers or {}

    def ask(system: str, text: str) -> str:
        if text in answers:
            return answers[text]
        for line in text.splitlines():
            stripped = line.strip()
            if len(stripped) > 3 and any(c.isalpha() for c in stripped):
                return stripped
        return default

    return ask


def get_asker() -> tuple[Asker, bool]:
    """Whichever provider has a key, else the offline stub.

    Returns (asker, is_live) so callers can tell the user which they are getting rather
    than silently degrading. Set LLM_PROVIDER to force one.
    """
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    order = ([openai_asker] if provider == "openai" else
             [anthropic_asker] if provider == "anthropic" else
             [openai_asker, anthropic_asker])
    for build in order:
        try:
            return build(), True
        except Exception:
            continue
    return echo_asker(), False


def asker_from_key(key: str, model: str | None = None) -> Asker:
    """Build an asker from a key the visitor pasted, never from our own environment.

    The provider is read off the key's own prefix — Anthropic keys start `sk-ant-`, so
    anything else is treated as OpenAI. Construction does not verify the key; a bad one
    surfaces as an error on the first call, which the pipeline reports against that one
    document rather than failing the whole batch.
    """
    k = (key or "").strip()
    if k.startswith("sk-ant-"):
        return anthropic_asker(model, key=k)
    return openai_asker(model, key=k)
