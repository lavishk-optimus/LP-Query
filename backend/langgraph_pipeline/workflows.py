# from langgraph.graph import StateGraph, END
# from langgraph.prebuilt import ToolNode
# from typing_extensions import TypedDict
# from typing import Annotated, List
# from langchain_core.messages import BaseMessage
# from langgraph.graph.message import add_messages

# from nodes import agent_node, should_continue
# from tools import ALL_TOOLS

# class MessagesState(TypedDict):
#     messages: Annotated[List[BaseMessage], add_messages]


# class Workflow_class:

#     # @staticmethod
#     def create_multi_turn_workflow():
#         """Create a simple multi-turn workflow."""
#         workflow = StateGraph(MessagesState)
        
#         # Add nodes
#         workflow.add_node("agent", agent_node)
#         workflow.add_node("tools", ToolNode(ALL_TOOLS))
        
#         # Set entry point and edges
#         workflow.set_entry_point("agent")
#         workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "END": END})
#         workflow.add_edge("tools", "agent")
        
#         return workflow.compile()

# # def create_streaming_workflow():
# #     """Create a workflow optimized for streaming responses."""
# #     return create_multi_turn_workflow()  # Same workflow, but we'll use .stream() method






from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict
from typing import Annotated, List, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
import threading
import logging

from .nodes import agent_node, should_continue
from .tools import ALL_TOOLS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessagesState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

class WorkflowSingleton:
    """Singleton class for workflow management"""
    
    _instance: Optional['WorkflowSingleton'] = None
    _lock = threading.Lock()
    _workflow = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(WorkflowSingleton, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    try:
                        logger.info("Initializing workflow singleton...")
                        self._workflow = self._create_workflow()
                        self._initialized = True
                        logger.info("Workflow singleton initialized successfully")
                    except Exception as e:
                        logger.error(f"Failed to initialize workflow: {e}")
                        raise RuntimeError(f"Workflow initialization failed: {e}")
    
    def _create_workflow(self):
        """Create the workflow graph"""
        try:
            workflow = StateGraph(MessagesState)
            
            # Add nodes
            workflow.add_node("agent", agent_node)
            workflow.add_node("tools", ToolNode(ALL_TOOLS))
            
            # Set entry point and edges
            workflow.set_entry_point("agent")
            workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "END": END})
            workflow.add_edge("tools", "agent")
            
            return workflow.compile()
        
        except Exception as e:
            logger.error(f"Error creating workflow: {e}")
            raise
    
    def get_workflow(self):
        """Get the compiled workflow"""
        if not self._initialized or self._workflow is None:
            raise RuntimeError("Workflow not properly initialized")
        return self._workflow
    
    def is_initialized(self) -> bool:
        """Check if workflow is initialized"""
        return self._initialized and self._workflow is not None
    
    def reset(self):
        """Reset the singleton (useful for testing or reconfiguration)"""
        with self._lock:
            logger.info("Resetting workflow singleton...")
            self._workflow = None
            self._initialized = False
            logger.info("Workflow singleton reset")

# Global singleton instance
workflow_singleton = WorkflowSingleton()

class Workflow_class:
    """Legacy wrapper class for backward compatibility"""
    
    @staticmethod
    def create_multi_turn_workflow():
        """Get the singleton workflow instance"""
        return workflow_singleton.get_workflow()

def get_workflow():
    """Factory function to get workflow instance"""
    return workflow_singleton.get_workflow()

def create_streaming_workflow():
    """Create a workflow optimized for streaming responses."""
    return get_workflow()  # Same workflow, but we'll use .stream() method