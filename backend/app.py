from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
# from langgraph_pipeline.agents.sql_agent import sql_agent_singleton_instance
from langgraph_pipeline.workflows import workflow_singleton, get_workflow
from langchain_core.messages import HumanMessage
from typing import Optional
import logging

# Set u
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SQL Query API")

class QueryRequest(BaseModel):
    """Request model for natural language query"""
    query: str
    user_id: Optional[str] = "default_user"

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting up application...")
    
    # Check if workflow is properly initialized
    if not workflow_singleton.is_initialized():
        logger.error("Workflow singleton failed to initialize")
        raise RuntimeError("Failed to initialize workflow")
    
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down application...")
    # Add any cleanup logic here
    logger.info("Application shutdown complete")





# @app.get("/")
# def health_check():
#     """Health check endpoint"""
#     workflow_status = "initialized" if workflow_singleton.is_initialized() else "not_initialized"
#     return {
#         "status": "ok",
#         "workflow_status": workflow_status
#     }

# @app.get("/status")
# def get_status():
#     """Detailed status endpoint"""
#     return {
#         "workflow_initialized": workflow_singleton.is_initialized(),
#         "sql_agent_available": hasattr(sql_agent_singleton_instance, 'get_response')
#     }

# @app.post("/api/query")
# async def query_database(request: QueryRequest):
#     """
#     Execute a natural language query against the database
    
#     Example request:
#         {
#             "query": "How many users are in the system?",
#             "user_id": "user123"
#         }
#     """
#     try:
#         # Call SQL agent with the query
#         response = await sql_agent_singleton_instance.get_response(
#             user_query=request.query,
#             user_id=request.user_id,
#             modules=[]  # Empty list since we're not using modules for this endpoint
#         )
        
#         return response
#     except Exception as e:
#         logger.error(f"Error in /api/query: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Error processing query: {str(e)}"
#         )







@app.post("/api/test_chat")
async def test_chat(request: QueryRequest):
    """Test the workflow with a simple chat message"""
    try:
        # Process query using workflow singleton
        response = await workflow_singleton.process_query(request.query)
        
        # Extract the final response
        final_message = response['messages'][-1] if response.get('messages') else None
        final_content = final_message.content if final_message else "No response generated"
        
        return {
            "query": request.query,
            "response": final_content,
            "user_id": request.user_id
        }
        
    except Exception as e:
        logger.error(f"Error in /api/test_chat: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat: {str(e)}"
        )
