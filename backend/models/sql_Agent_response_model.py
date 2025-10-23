from pydantic import BaseModel

class SqlAgentResponseModel(BaseModel):
    summary: str
    total_modules: int
    completed_modules: int

