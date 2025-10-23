from datetime import datetime
import logging
import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
# from langgraph_pipeline.agents.sql_agent import sql_agent_singleton_instance
from typing import List, Optional
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
load_dotenv()
app = FastAPI(title="SQL Query API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
cosmos_conn = os.getenv("cdblpqueryccprod01_DOCUMENTDB")
cosmos_client = CosmosClient.from_connection_string(cosmos_conn)
database = cosmos_client.get_database_client("lpquery")
container = database.get_container_client("alert_preferences")
schedule_email_container = database.get_container_client("email_schedule")
 
class QueryRequest(BaseModel):
    """Request model for natural language query"""
    query: str
    user_id: Optional[str] = "default_user"

class AlertPreference(BaseModel):
    user_id: str = Field(..., example="test123")
    user_email: Optional[str] = Field(None, example="user@example.com")
    alert_type: str = Field(default="NAV", example="IRR")    
    threshold_type: str = Field(default="Above", example="Above")  
    threshold_value: float = Field(default=5, example=5)
    funds: List[str] = Field(..., example=["Harbor Growth Fund III", "Equity Alpha"])
    frequency: str = Field(default="immediate", example="immediate")     

class EmailScheduleRequest(BaseModel):
    user_id: str = Field(..., description="User ID to filter data")
    email: str = Field(..., description="Recipient email address")
    send_date: str = Field(..., description="Date on which to send email (YYYY-MM-DD)")

@app.get("/")
def health_check():
    return {"status": "ok"}

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
      
#         response = await sql_agent_singleton_instance.get_response(
#             user_query=request.query,
#             user_id=request.user_id,
#             modules=[]  
#         )
        
#         return response
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Error processing query: {str(e)}"
#         )

@app.post("/alert-preferences")
def store_alert_preferences(pref: AlertPreference):
    """
    Store user alert preferences in Cosmos DB.
    """
    try:
        if not pref.user_id or not pref.funds:
            raise HTTPException(status_code=400, detail="'user_id' and 'funds' are required.")

        alert_id = f"alert_{pref.user_id}_{str(uuid.uuid4())}"

        doc = {
            "id": alert_id,
            "user_id": pref.user_id,
            "user_email": pref.user_email,
            "alert_type": pref.alert_type,
            "threshold_type": pref.threshold_type,
            "threshold_value": pref.threshold_value,
            "funds": pref.funds,
            "frequency": pref.frequency
        }

        container.upsert_item(doc)

        logging.info(f"✅ Alert preferences saved successfully for user {pref.user_id}")

        return {"message": f"✅ Alert preferences saved successfully for user {pref.user_id}"}

    except Exception as e:
        logging.error(f"Error saving alert preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/schedule-email")
async def schedule_email(req: EmailScheduleRequest):
    # Validate date
    try:
        datetime.strptime(req.send_date, "%Y-%m-%d")
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    schedule_item = {
        "id": f"{req.user_id}-{req.send_date}",
        "type": "schedule",
        "user_id": req.user_id,
        "email": req.email,
        "send_date": req.send_date,
        "status": "pending"
    }

    schedule_email_container.upsert_item(schedule_item)

    return {
        "message": f"Email scheduled for {req.send_date} for user {req.user_id}",
        "data": schedule_item
    }    

