"""Azure OpenAI provider -- the real LLM used in the live demo (PRD s6, s13)."""

from __future__ import annotations

from .base import LLMError


class AzureOpenAIProvider:
    name = "azure_openai"

    def __init__(self, settings):
        missing = [
            k for k, v in {
                "AZURE_OPENAI_ENDPOINT": settings.azure_openai_endpoint,
                "AZURE_OPENAI_API_KEY": settings.azure_key(),
                "AZURE_OPENAI_DEPLOYMENT": settings.azure_openai_deployment,
            }.items() if not v
        ]
        if missing:
            raise LLMError(f"azure_openai provider missing config: {', '.join(missing)}")

        try:
            from openai import AzureOpenAI
        except ImportError as e:  # pragma: no cover
            raise LLMError("the 'openai' package is required for LLM_PROVIDER=azure_openai") from e

        self._deployment = settings.azure_openai_deployment
        self._max_tokens = settings.llm_max_tokens
        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_key(),
            api_version=settings.azure_openai_api_version,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )

    def complete(self, system: str, user: str) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self._deployment,
                temperature=0,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as e:  # openai raises many subclasses; treat all as call failure
            raise LLMError(f"Azure OpenAI call failed: {e}") from e

        choice = (resp.choices or [None])[0]
        content = getattr(getattr(choice, "message", None), "content", None)
        if not content:
            raise LLMError("Azure OpenAI returned an empty response")
        return content
