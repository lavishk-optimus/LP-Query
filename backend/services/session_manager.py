from typing import Dict, Any
from uuid import uuid4
from datetime import datetime, timezone
from services.cosmos_client import cosmos_client_singleton_instance, ContainerType
from services.telemetry_client import telemetry_client
from constants import SESSION_DURATION

class SessionManager:
    def __init__(self):
        self.cosmos_client = cosmos_client_singleton_instance
        telemetry_client.log_info("Session Manager initialized")

    async def get_or_create_session(self, user_id: str) -> Dict[str, Any]:
        """
        Gets an existing session for the user or creates a new one if none exists.
        If existing session is older than SESSION_DURATION, creates a new session.
        
        Args:
            user_id (str): The ID of the user to get/create a session for
            
        Returns:
            Dict[str, Any]: The session data including:
                - id: The session ID (used as partition key)
                - user_id: The user ID
                - session_id: Unique session identifier
                - is_welcomed: Whether the welcome message has been shown
                - created_at: Timestamp when session was created
        """
        try:
            telemetry_client.log_info(f"Fetching session for user {user_id}")
            sessions = await self.cosmos_client.find_items_by_filter(
                container_type=ContainerType.SESSION,
                filters={"user_id": user_id}
            )

            current_time = datetime.now(timezone.utc)

            if sessions:
                session = sessions[0]
                created_at = datetime.fromisoformat(session["created_at"].replace("Z", "+00:00"))
                session_age = (current_time - created_at).total_seconds()
                
                telemetry_client.log_info(f"Session age for user {user_id}: {session_age} seconds", {
                    "user_id": user_id,
                    "session_id": session["session_id"],
                    "session_age_seconds": session_age
                })
                
                if session_age > SESSION_DURATION:
                    telemetry_client.log_info(f"Session expired for user {user_id}, creating new session", {
                        "user_id": user_id,
                        "old_session_id": session["session_id"],
                        "session_age_seconds": session_age
                    })
                    
                    old_session_id = session["session_id"]
                    session["session_id"] = str(uuid4())
                    session["created_at"] = current_time.isoformat().replace("+00:00", "Z")
                    session["is_welcomed"] = False
                    
                    success = await self.cosmos_client.save_item(
                        container_type=ContainerType.SESSION,
                        item=session,
                        partition_key=session["id"]
                    )
                    
                    if success:
                        telemetry_client.log_info(f"Updated expired session for user {user_id}", {
                            "user_id": user_id,
                            "old_session_id": old_session_id,
                            "new_session_id": session["session_id"],
                            "reason": "session_expired",
                            "session_age_seconds": session_age
                        })
                        return session
                    else:
                        telemetry_client.log_warning(f"Failed to update expired session for user {user_id}")
                        raise Exception("Failed to update session")
                
                telemetry_client.log_info(f"Retrieved existing session for user {user_id}", {
                    "user_id": user_id,
                    "session_id": session["session_id"],
                    "is_welcomed": session["is_welcomed"],
                    "session_age_seconds": session_age
                })
                return session

            telemetry_client.log_info(f"No session found for user {user_id}, creating new session")
            new_session = {
                "id": user_id,
                "user_id": user_id,
                "session_id": str(uuid4()),
                "is_welcomed": True,
                "created_at": current_time.isoformat().replace("+00:00", "Z")
            }

            success = await self.cosmos_client.save_item(
                container_type=ContainerType.SESSION,
                item=new_session,
                partition_key=user_id
            )

            if success:
                telemetry_client.log_info(f"Created new session for user {user_id}", {
                    "user_id": user_id,
                    "session_id": new_session["session_id"],
                    "reason": "first_session"
                })
                return new_session
            else:
                telemetry_client.log_warning(f"Failed to create new session for user {user_id}")
                raise Exception("Failed to create new session")

        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": str(e),
                "user_id": user_id,
                "operation": "get_or_create_session"
            })
            raise Exception(f"Error managing session for user {user_id}: {str(e)}")

    async def update_welcome_status(self, user_id: str, is_welcomed: bool = True) -> bool:
        """
        Updates the is_welcomed status for a user's session.
        
        Args:
            user_id (str): The ID of the user whose session to update
            is_welcomed (bool): The new welcome status (defaults to True)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            telemetry_client.log_info(f"Updating welcome status for user {user_id}", {
                "user_id": user_id,
                "is_welcomed": is_welcomed
            })
            
            sessions = await self.cosmos_client.find_items_by_filter(
                container_type=ContainerType.SESSION,
                filters={"user_id": user_id}
            )

            if not sessions:
                telemetry_client.log_warning(f"No session found for user {user_id} when updating welcome status")
                return False

            session = sessions[0]
            session["is_welcomed"] = is_welcomed

            success = await self.cosmos_client.save_item(
                container_type=ContainerType.SESSION,
                item=session,
                partition_key=session["id"]
            )

            if success:
                telemetry_client.log_info(f"Updated welcome status for user {user_id}", {
                    "user_id": user_id,
                    "session_id": session["session_id"],
                    "is_welcomed": is_welcomed
                })
                return True
            else:
                telemetry_client.log_warning(f"Failed to update welcome status for user {user_id}")
                return False

        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": str(e),
                "user_id": user_id,
                "operation": "update_welcome_status"
            })
            return False

    async def get_welcome_status(self, user_id: str) -> bool:
        """
        Checks if the user exists in the database.
        
        Args:
            user_id (str): The ID of the user to check existence for
            
        Returns:
            bool: True if user exists in database, False otherwise
        """
        try:
            telemetry_client.log_info(f"Checking if user exists in database: {user_id}")
            
            sessions = await self.cosmos_client.find_items_by_filter(
                container_type=ContainerType.SESSION,
                filters={"user_id": user_id}
            )

            user_exists = len(sessions) > 0
            
            telemetry_client.log_info(f"User existence check for {user_id}: {'exists' if user_exists else 'not found'}", {
                "user_id": user_id,
                "user_exists": user_exists
            })

            return user_exists

        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": str(e),
                "user_id": user_id,
                "operation": "get_welcome_status"
            })
            raise Exception(f"Error checking user existence for user {user_id}: {str(e)}")

session_manager_singleton_instance = SessionManager()