from langchain_core.tools import StructuredTool
from pydantic import BaseModel


class AddNumbersInput(BaseModel):
    """Input schema for the add_numbers tool."""

    a: int
    b: int


async def add_numbers(a: int, b: int) -> int:
    """Add two integers and return their sum."""
    return a + b


add_numbers_tool = StructuredTool.from_function(
    coroutine=add_numbers,
    name="add_numbers",
    description="Add two integers together and return the sum.",
    args_schema=AddNumbersInput,
)
