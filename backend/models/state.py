from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class Message(TypedDict):
    id: str
    type: str
    content: str

class State(TypedDict):
    user_id: str
    session_id: str
    messages: Annotated[list[Message], add_messages]
