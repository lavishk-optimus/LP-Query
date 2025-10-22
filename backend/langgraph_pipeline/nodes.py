from typing import Dict, Any
from .agents.test_agent import create_azure_llm
from .tools import ALL_TOOLS

def agent_node(state):
    """LLM agent node."""
    llm = create_azure_llm(ALL_TOOLS)
    messages = state['messages']
    response = llm.invoke(messages)
    return {"messages": [response]}

def should_continue(state):
    """Decide whether to continue with tools or end."""
    messages = state['messages']
    last_message = messages[-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return "END"