import datetime
import json
import logging
import os
import uuid
from models.mail_service import AlertPreference, EmailScheduleRequest
from services.cosmos_client import cosmos_client_singleton_instance, ContainerType
from services.session_manager import session_manager_singleton_instance
from services.centralized_logging_service import centralized_logger
from models.state import State
from fastapi import APIRouter,HTTPException
from langgraph_pipeline.query_orchestrator import QueryOrchestrator
from fastapi.responses import RedirectResponse
from models.query_request_model import Query
from utils.api_response import ApiResponse
from langchain.schema import HumanMessage
from azure.cosmos import CosmosClient
from fastapi import Request
from services.telemetry_client import telemetry_client
import time
  
router = APIRouter()

cosmos_conn = os.getenv("cdblpqueryccprod01_DOCUMENTDB")
cosmos_client = CosmosClient.from_connection_string(cosmos_conn)
database = cosmos_client.get_database_client("lpquery")
container = database.get_container_client("alert_preferences")
schedule_email_container = database.get_container_client("email_schedule")

@router.get("/")
def docs_redirect():
    return RedirectResponse(url="/docs")
 
@router.get("/health")
def health_check():
    operation_id = f"health_check_{int(time.time() * 1000)}"
    centralized_logger.start_operation(operation_id)
    centralized_logger.simple_log(operation_id, success=True)
    return ApiResponse(success = True, data = [{"response": "Server is up!"}], status_code = 200).response()
 
@router.post("/query")
async def execute_query(query: Query):
    """
    Execute a query for a user. This endpoint:
    1. Gets or creates a session for the user
    2. Executes the query using the langgraph pipeline
   
    The session is automatically managed - if it's older than SESSION_DURATION,
    a new session will be created and is_welcomed will be reset to false.
    """
    try:
        user_id = query.user_id
        operation_id = f"query_{user_id}_{int(time.time() * 1000)}"
        centralized_logger.start_operation(operation_id)

        session = await session_manager_singleton_instance.get_or_create_session(user_id)
        session_id = session["session_id"]
 
        if not session["is_welcomed"]:
            await session_manager_singleton_instance.update_welcome_status(user_id, True)
            centralized_logger.simple_log(operation_id, success=True, user_id=user_id, session_id=session_id, type="welcome_card")
            session["is_welcomed"] = True
            await session_manager_singleton_instance.cosmos_client.save_item(
                container_type=ContainerType.SESSION,
                item=session,
                partition_key=session["user_id"]
            )
 
        message = HumanMessage(content=query.question)
        state = State(
            user_id=user_id,
            session_id=session_id,
            messages=[message]
        )
 
        id = f'{user_id}${session_id}'
        config = {"configurable": {"thread_id": id}}
 
        graph_async = await QueryOrchestrator().initialize_orchestrator()
        result = await graph_async.ainvoke(state, config)
        response_data = result["messages"][-1].content
 
        try:
            parsed_response = json.loads(response_data)
        except (TypeError, json.JSONDecodeError):
            parsed_response = response_data
 
 
        centralized_logger.simple_log(operation_id, success=True, user_id=user_id, session_id=session_id)
        return ApiResponse(
            success=True,
            data=[{"response": parsed_response}],
            status_code=200
        ).response()
 
    except ValueError as e:
        user_id = getattr(query, 'user_id', "unknown")
        operation_id = f"query_error_{user_id}_{int(time.time() * 1000)}"
        centralized_logger.start_operation(operation_id)
        centralized_logger.log_validation_error(operation_id, str(e), user_id=user_id)
        return ApiResponse(
            success=False,
            data=[{"error": str(e)}],
            status_code=400
        ).response()
    except Exception as e:
        user_id = getattr(query, 'user_id', "unknown")
        operation_id = f"query_exception_{user_id}_{int(time.time() * 1000)}"
        centralized_logger.start_operation(operation_id)
        centralized_logger.log_exception(operation_id, e, user_id=user_id, 
                                        error=f"Error during query execution: {e}")
        return ApiResponse(
            success=False,
            data=[{"error": "An error occurred while processing your request."}],
            status_code=500
        ).response()
 
@router.post("/alert-preferences")
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
    

@router.post("/schedule-email")
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
