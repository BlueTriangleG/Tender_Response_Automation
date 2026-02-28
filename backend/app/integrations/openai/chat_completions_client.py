"""Thin wrapper around the OpenAI chat completions API."""

from openai import AsyncOpenAI

from app.core.config import settings


class OpenAIChatCompletionsClient:
    """Expose a narrow interface that the rest of the app can mock in tests."""

    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI()
        self._model = model or settings.openai_chat_model

    async def create_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Send a plain chat completion request and return the first text response."""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    async def create_json_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Send a completion request that hard-requires a JSON object response."""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""
