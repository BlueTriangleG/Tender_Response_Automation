from openai import AsyncOpenAI

from app.core.config import settings


class OpenAIEmbeddingsClient:
    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI()
        self._model = model or settings.openai_embedding_model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in response.data]
