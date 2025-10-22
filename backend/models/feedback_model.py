from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
import datetime
 
class FeedbackRequest(BaseModel):
    user_id: str = Field(..., description="User ID who is providing feedback")
    feedbackText: Optional[str] = Field(
        default="",
        description="The feedback text content extracted from feedback.actionValue.feedback"
    )
    feedbackType: Optional[str] = Field(
        default=None,
        description="Type of feedback (like/dislike) extracted from feedback.actionValue.reaction"
    )
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat(), description="ISO timestamp when feedback was created")
   
    @validator('timestamp')
    def validate_timestamp(cls, v):
        if v is None:
            return datetime.datetime.utcnow().isoformat()
        try:
            datetime.datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('timestamp must be a valid ISO format string')
 
class FeedbackResponse(BaseModel):
    message: str
    feedback_id: str
    session_id: Optional[str] = None
    success: bool = True
 