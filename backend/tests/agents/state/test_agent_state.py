from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state.agent_state import smart_message_reducer


def test_smart_message_reducer_appends_by_default() -> None:
    old = [HumanMessage(content="hello")]
    new = [AIMessage(content="world")]

    result = smart_message_reducer(old, new)

    assert len(result) == 2
    assert result[0].content == "hello"
    assert result[1].content == "world"


def test_smart_message_reducer_replaces_when_first_message_has_replace_flag() -> None:
    old = [HumanMessage(content="stale"), HumanMessage(content="also stale")]
    marker = AIMessage(content="")
    marker._replace = True  # type: ignore[attr-defined]
    fresh = AIMessage(content="fresh summary")

    result = smart_message_reducer(old, [marker, fresh])

    # old list is discarded; marker itself is filtered out; only fresh remains
    assert len(result) == 1
    assert result[0].content == "fresh summary"
