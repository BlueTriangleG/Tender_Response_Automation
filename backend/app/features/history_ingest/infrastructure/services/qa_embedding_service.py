"""Embedding adapter for normalized QA text."""

from openai import AsyncOpenAI

from app.integrations.openai.embeddings_client import OpenAIEmbeddingsClient


class QaEmbeddingService:
    """Accept either a raw AsyncOpenAI client or the app's embeddings wrapper."""

    def __init__(
        self,
        client: AsyncOpenAI | OpenAIEmbeddingsClient | None = None,
        model: str | None = None,
    ) -> None:
        if client is None:
            self._client = OpenAIEmbeddingsClient(model=model)
        elif hasattr(client, "embed_texts"):
            self._client = client
        else:
            self._client = OpenAIEmbeddingsClient(client=client, model=model)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for QA records before persistence."""

        return await self._client.embed_texts(texts)
