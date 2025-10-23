from typing import List, Optional
from pydantic import BaseModel, Field

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