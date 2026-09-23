import asyncio
import math
import random
import re
from typing import Any, Protocol, cast

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError
from app.schemas.errors import ErrorCode


class LLMProvider(Protocol):
    async def generate(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]: ...


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


class GeminiProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _post(self, method: str, data: dict[str, Any], code: ErrorCode) -> dict[str, Any]:
        key = self.settings.gemini_api_key.get_secret_value()
        if not key:
            raise AppError(code, "Gemini is not configured. Set GEMINI_API_KEY on the server.")
        # Gemini quotas apply per project, so a valid key can still be rate-limited
        # while embedding a repository. Use bounded exponential backoff for these
        # transient responses, matching the provider's recommended behavior.
        attempts = self.settings.gemini_retry_attempts
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=45) as client:
                    response = await client.post(
                        "https://generativelanguage.googleapis.com/v1beta/models/" + method,
                        headers={"x-goog-api-key": key},
                        json=data,
                    )
                if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
                if response.status_code == 429:
                    raise AppError(
                        code, "Gemini rate limit was reached. Retry repository analysis shortly."
                    )
                if response.status_code == 404:
                    raise AppError(
                        code,
                        "The configured Gemini generation model is unavailable. "
                        "Set GEMINI_GENERATION_MODEL to a model returned by Gemini's models API.",
                    )
                if response.status_code != 200:
                    raise AppError(
                        code, "Gemini request failed or quota was exceeded. Retry later."
                    )
                return cast(dict[str, Any], response.json())
            except (httpx.HTTPError, ValueError):
                if attempt == attempts - 1:
                    raise AppError(code, "Gemini is unavailable. Retry later.") from None
                await asyncio.sleep(min(2**attempt, 60) + random.uniform(0, 0.25))
        raise AppError(code, "Gemini request failed.")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        """Prefer Gemini's retry window, then use bounded exponential backoff."""
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return max(float(retry_after), 0)
            except ValueError:
                pass
        # Google errors can include a protobuf RetryInfo duration such as "12.5s".
        match = re.search(r'"retryDelay"\s*:\s*"([0-9.]+)s"', response.text)
        if match:
            return float(match.group(1))
        return min(2**attempt, 60) + random.uniform(0, 0.25)

    async def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        vectors = []
        model = self.settings.embedding_model
        for offset in range(0, len(texts), 32):
            batch = texts[offset : offset + 32]
            data = await self._post(
                model + ":batchEmbedContents",
                {
                    "requests": [
                        {
                            "model": "models/" + model,
                            "content": {"parts": [{"text": text}]},
                            "taskType": "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT",
                            "outputDimensionality": 768,
                        }
                        for text in batch
                    ]
                },
                ErrorCode.EMBEDDING_ERROR,
            )
            try:
                embeddings = data["embeddings"]
                if len(embeddings) != len(batch):
                    raise ValueError
                for item in embeddings:
                    values = item["values"]
                    norm = math.sqrt(sum(v * v for v in values))
                    if len(values) != 768 or not math.isfinite(norm) or norm == 0:
                        raise ValueError
                    vectors.append([v / norm for v in values])
            except (KeyError, TypeError, ValueError):
                raise AppError(
                    ErrorCode.EMBEDDING_ERROR, "Gemini returned invalid embeddings."
                ) from None
            if offset + 32 < len(texts):
                await asyncio.sleep(0.25)
        return vectors

    async def generate(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        import json

        data = await self._post(
            self.settings.gemini_generation_model + ":generateContent",
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 4096,
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema,
                },
            },
            ErrorCode.AI_PROVIDER_ERROR,
        )
        try:
            return cast(
                dict[str, Any], json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
            )
        except (KeyError, IndexError, ValueError, TypeError):
            raise AppError(
                ErrorCode.AI_PROVIDER_ERROR, "Gemini returned an invalid response."
            ) from None
