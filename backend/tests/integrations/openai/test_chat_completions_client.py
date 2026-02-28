from app.integrations.openai.chat_completions_client import OpenAIChatCompletionsClient


class FakeChatResponseMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChatChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeChatResponseMessage(content)


class FakeChatResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChatChoice(content)]


class FakeAsyncOpenAI:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.chat = self
        self.completions = self

    async def create(self, *, model: str, messages: list[dict[str, str]]) -> FakeChatResponse:
        self.calls.append({"model": model, "messages": messages})
        return FakeChatResponse('{"ok":true}')


async def test_chat_completions_client_calls_openai_sdk() -> None:
    client = FakeAsyncOpenAI()
    adapter = OpenAIChatCompletionsClient(client=client, model="gpt-4o-mini")

    result = await adapter.create_json_completion(
        system_prompt="Return JSON only",
        user_prompt="Detect columns",
    )

    assert result == '{"ok":true}'
    assert client.calls == [
        {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Return JSON only"},
                {"role": "user", "content": "Detect columns"},
            ],
        }
    ]
