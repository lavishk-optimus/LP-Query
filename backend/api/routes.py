import datetime
import json
from services.cosmos_client import cosmos_client_singleton_instance, ContainerType
from services.session_manager import session_manager_singleton_instance
from services.centralized_logging_service import centralized_logger
from models.state import State
from fastapi import APIRouter
from langgraph_pipeline.query_orchestrator import QueryOrchestrator
from fastapi.responses import RedirectResponse
from models.query_request_model import Query
from models.feedback_model import FeedbackRequest
from utils.api_response import ApiResponse
from langchain.schema import HumanMessage
from fastapi import Request
from services.telemetry_client import telemetry_client
import time
 
router = APIRouter()
 
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

            return ApiResponse(
                success=True,
                data=[{"response": "WELCOME CARD REQUIRED"}],
                status_code=200
            ).response()
 
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
 
@router.post("/feedbackendpoint")
async def submit_feedback(feedback: FeedbackRequest):
    """
    1. Submit user feedback from adaptive card.
    2. Likes and dislikes are stored separately along with free-text feedback.
 
    """
    operation_id = f"feedback_{feedback.user_id}_{int(time.time() * 1000)}"
    centralized_logger.start_operation(operation_id)
    
    try:
        try:
            session = await session_manager_singleton_instance.get_or_create_session(feedback.user_id)
            session_id = session["session_id"]
        except Exception as session_error:
            session_id = None  
       
        feedback_item = {
            "id": f'{feedback.user_id}_{int(time.time() * 1000)}',  
            "user_id": feedback.user_id,
            "session_id": session_id,
            "feedbackType": feedback.feedbackType,
            "feedbackText": feedback.feedbackText,
        }
 
        await cosmos_client_singleton_instance.save_item(
            container_type=ContainerType.FEEDBACK,
            item=feedback_item,
            partition_key=feedback.user_id
        )
 
        centralized_logger.simple_log(operation_id, success=True, user_id=feedback.user_id, session_id=session_id)
        return ApiResponse(
            success=True,
            status_code=200
        ).response()
 
    except ValueError as e:
        centralized_logger.log_validation_error(operation_id, str(e), 
                                              user_id=feedback.user_id if hasattr(feedback, 'user_id') else 'unknown')
        return ApiResponse(
            success=False,
            data=[{"error": str(e)}],
            status_code=400
        ).response()
    except Exception as e:
        centralized_logger.log_exception(operation_id, e, 
                                        user_id=feedback.user_id if hasattr(feedback, 'user_id') else 'unknown',
                                        error=f"Error storing feedback: {e}")
        return ApiResponse(
            success=False,
            data=[{"error": "An error occurred while submitting your feedback."}],
            status_code=500
        ).response()
 

@router.get("/get_welcome_status")
async def get_welcome_status(user_id: str):
    """
    Check if the user exists in the database.
    Returns whether the user exists (true/false).
    """
    operation_id = f"get_welcome_status_{user_id}_{int(time.time() * 1000)}"
    centralized_logger.start_operation(operation_id)
    
    try:
        if not user_id or not user_id.strip():
            raise ValueError("user_id is required and cannot be empty")

        user_exists = await session_manager_singleton_instance.get_welcome_status(user_id.strip())

        centralized_logger.simple_log(operation_id, success=True, user_id=user_id, user_exists=user_exists)
        return ApiResponse(
            success=True,
            data=[{
                "message": "User existence checked successfully",
                "user_id": user_id,
                "user_exists": user_exists
            }],
            status_code=200
        ).response()

    except ValueError as e:
        centralized_logger.log_validation_error(operation_id, str(e), user_id=user_id if user_id else 'empty')
        return ApiResponse(
            success=False,
            data=[{"error": str(e)}],
            status_code=400
        ).response()
    except Exception as e:
        centralized_logger.log_exception(operation_id, e, user_id=user_id if user_id else 'unknown')
        return ApiResponse(
            success=False,
            data=[{"error": "An error occurred while checking user existence."}],
            status_code=500
        ).response()
   