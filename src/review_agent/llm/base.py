"""LLM provider protocol + prompt loading.

One real provider is used live in the demo (``azure_openai``); ``mock`` exists only for
tests and offline dev (PRD s6).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LLMError(RuntimeError):
    """Provider call failed (network, auth, quota, timeout)."""


class LLMProvider(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str:
        """Return the model's raw text response (expected to be a JSON object)."""


def load_prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


def system_prompt() -> str:
    return load_prompt("system.txt")


def user_prompt(*, context: str, target_file: str, pr_id, repo: str,
                target_branch: str, source_branch: str) -> str:
    return load_prompt("java_review.txt").format(
        context=context,
        target_file=target_file,
        pr_id=pr_id if pr_id is not None else "?",
        repo=repo or "?",
        target_branch=target_branch or "?",
        source_branch=source_branch or "?",
    )


def build_provider(settings):
    provider = (settings.llm_provider or "mock").lower()
    if provider == "mock":
        from .mock import MockProvider

        return MockProvider()
    if provider in ("azure_openai", "azure"):
        from .azure_openai import AzureOpenAIProvider

        return AzureOpenAIProvider(settings)
    raise LLMError(f"unknown LLM_PROVIDER: {settings.llm_provider!r} (use 'azure_openai' or 'mock')")
