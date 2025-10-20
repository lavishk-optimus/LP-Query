from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict
from typing import Annotated, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from nodes import agent_node, should_continue
from tools import ALL_TOOLS

class MessagesState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

def create_multi_turn_workflow():
    """Create a simple multi-turn workflow."""
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(ALL_TOOLS))
    
    # Set entry point and edges
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "END": END})
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()

def create_streaming_workflow():
    """Create a workflow optimized for streaming responses."""
    return create_multi_turn_workflow()  # Same workflow, but we'll use .stream() method