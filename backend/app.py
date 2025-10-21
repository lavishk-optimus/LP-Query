from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langgraph_pipeline.agents.sql_agent import sql_agent_singleton_instance
from typing import Optional

app = FastAPI(title="SQL Query API")

class QueryRequest(BaseModel):
    """Request model for natural language query"""
    query: str
    user_id: Optional[str] = "default_user"

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.post("/api/query")
async def query_database(request: QueryRequest):
    """
    Execute a natural language query against the database
    
    Example request:
        {
            "query": "How many users are in the system?",
            "user_id": "user123"
        }
    """
    try:
        # Call SQL agent with the query
        response = await sql_agent_singleton_instance.get_response(
            user_query=request.query,
            user_id=request.user_id,
            modules=[]  # Empty list since we're not using modules for this endpoint
        )
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

