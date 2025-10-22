import time
from typing import Dict, Any, Optional
from services.telemetry_client import telemetry_client


class CentralizedLoggingService:
    """
    Centralized logging service that automatically handles common dimensions
    and reduces code duplication in route handlers.
    """
    
    def __init__(self):
        self.telemetry_client = telemetry_client
        self._start_times: Dict[str, float] = {}
    
    def start_operation(self, operation_id: str) -> None:
        """
        Start timing an operation. Call this at the beginning of your endpoint.
        
        Args:
            operation_id: Unique identifier for this operation (can be request ID, user ID, etc.)
        """
        self._start_times[operation_id] = time.time()
    
    def _get_response_time(self, operation_id: str) -> float:
        """Calculate response time for an operation."""
        start_time = self._start_times.get(operation_id, time.time())
        return round((time.time() - start_time) * 1000, 2)
    
    def _build_dimensions(self, operation_id: str, user_id: Optional[str] = None, 
                         session_id: Optional[str] = None, **extra_dimensions) -> Dict[str, Any]:
        """
        Build common dimensions dictionary with response time and optional fields.
        
        Args:
            operation_id: Operation identifier
            user_id: Optional user ID
            session_id: Optional session ID
            **extra_dimensions: Any additional dimensions to include
        """
        dimensions = {
            "response_time_ms": self._get_response_time(operation_id),
            **extra_dimensions
        }
        
        if user_id:
            dimensions["user_id"] = user_id
        if session_id:
            dimensions["session_id"] = session_id
            
        # Clean up the start time
        self._start_times.pop(operation_id, None)
        
        return dimensions
    
    def log_completion(self, operation_id: str, message: str, user_id: Optional[str] = None, 
                      session_id: Optional[str] = None, **extra_dimensions) -> None:
        """
        Log operation completion with response time (only for operations that might take time).
        
        Args:
            operation_id: Operation identifier
            message: Completion message
            user_id: Optional user ID
            session_id: Optional session ID
            **extra_dimensions: Any additional dimensions
        """
        dimensions = self._build_dimensions(operation_id, user_id, session_id, **extra_dimensions)
        self.telemetry_client.log_info(message, dimensions)
    
    def log_warning(self, operation_id: str, message: str, user_id: Optional[str] = None,
                   session_id: Optional[str] = None, **extra_dimensions) -> None:
        """
        Log a warning message with automatic common dimensions.
        
        Args:
            operation_id: Operation identifier
            message: Log message
            user_id: Optional user ID
            session_id: Optional session ID
            **extra_dimensions: Any additional dimensions
        """
        dimensions = self._build_dimensions(operation_id, user_id, session_id, **extra_dimensions)
        self.telemetry_client.log_warning(message, dimensions)
    
    def log_exception(self, operation_id: str, exception: Exception, user_id: Optional[str] = None,
                     session_id: Optional[str] = None, **extra_dimensions) -> None:
        """
        Log an exception with automatic common dimensions.
        
        Args:
            operation_id: Operation identifier
            exception: The exception to log
            user_id: Optional user ID
            session_id: Optional session ID
            **extra_dimensions: Any additional dimensions
        """
        dimensions = self._build_dimensions(operation_id, user_id, session_id, **extra_dimensions)
        self.telemetry_client.log_exception(exception, dimensions)
    
    def log_validation_error(self, operation_id: str, error: str, user_id: Optional[str] = None,
                           session_id: Optional[str] = None, **extra_dimensions) -> None:
        """
        Log a validation error with automatic error_type dimension.
        
        Args:
            operation_id: Operation identifier
            error: Error message
            user_id: Optional user ID
            session_id: Optional session ID
            **extra_dimensions: Any additional dimensions
        """
        dimensions = self._build_dimensions(
            operation_id, user_id, session_id, 
            error_type="validation", 
            **extra_dimensions
        )
        self.telemetry_client.log_warning(f"Validation error: {error}", dimensions)

    def simple_log(self, operation_id: str, success: bool = True, user_id: Optional[str] = None, 
                   **extra_dimensions) -> None:
        """
        Super simple logging - just log completion with timing for operations that might take time.
        Only call this ONCE at the end of your endpoint.
        
        Args:
            operation_id: Operation identifier
            success: Whether operation succeeded
            user_id: Optional user ID
            **extra_dimensions: Any additional dimensions
        """
        # Extract session_id from extra_dimensions to avoid duplicate argument error
        session_id = extra_dimensions.pop('session_id', None)
        dimensions = self._build_dimensions(operation_id, user_id, session_id, **extra_dimensions)
        status = "completed" if success else "failed"
        self.telemetry_client.log_info(f"Operation {status}", dimensions)


centralized_logger = CentralizedLoggingService()