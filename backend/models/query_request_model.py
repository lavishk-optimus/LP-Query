from pydantic import BaseModel, Field

class Query(BaseModel):
    """
    Request model for the query endpoint.
    Only requires user_id and question - session management is handled internally.
    """
    user_id: str = Field(..., description="The ID of the user making the query")
    question: str = Field(..., description="The question or query text from the user")
