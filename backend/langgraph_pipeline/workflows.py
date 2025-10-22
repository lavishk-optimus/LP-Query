from typing_extensions import TypedDict
from typing import Annotated, List, Optional
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
import threading
import logging
from .services.telemetry_client import telemetry_client
from .nodes import process_query

# Configure logging
logger = logging.getLogger(__name__)

class MessagesState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

class WorkflowManager:
    """Singleton class for managing the query workflow"""
    
    _instance: Optional['WorkflowManager'] = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(WorkflowManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    try:
                        logger.info("Initializing workflow manager...")
                        self._initialized = True
                        logger.info("Workflow manager initialized successfully")
                    except Exception as e:
                        logger.error(f"Failed to initialize workflow manager: {e}")
                        raise RuntimeError(f"Workflow initialization failed: {e}")
    
    async def process_query(self, query: str) -> dict:
        """
        Process a user query through the workflow
        """
        try:
            telemetry_client.log_info(f"Processing query: {query[:50]}...")
            
            # Create initial state with the query using HumanMessage
            state = {"messages": [HumanMessage(content=query)]}
            
            # Process the query
            result = await process_query(state)
            
            telemetry_client.log_info("Query processed successfully")
            return result
            
        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            telemetry_client.log_exception(e, {"error": error_msg})
            return {"messages": [AIMessage(content=error_msg)]}
    
    def is_initialized(self) -> bool:
        """Check if workflow is initialized"""
        return self._initialized

workflow_singleton = WorkflowManager()

def get_workflow():
    """Factory function to get workflow instance"""
    workflow = StateGraph(MessagesState)
    workflow.add_node("process", process_query)
    workflow.set_entry_point("process")
    workflow.add_edge("process", END)
    return workflow.compile()

async def process_streaming_query(query: str):
    """Process a query with streaming response capability"""
    return await workflow_singleton.process_query(query)