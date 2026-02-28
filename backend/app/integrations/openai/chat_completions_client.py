from openai import AsyncOpenAI

from app.core.config import settings


class OpenAIChatCompletionsClient:
    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI()
        self._model = model or settings.openai_csv_column_model

    async def create_json_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""
