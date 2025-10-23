from fastapi.responses import JSONResponse
from typing import Optional, List
from pydantic import BaseModel

class ApiResponseBase(BaseModel):
    success: bool
    errors: Optional[List[str]] = []
    data: Optional[List[dict]] = []
    status_code: int = 200

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "errors": self.errors,
            "data": self.data,
            "status_code": self.status_code
        }

class ApiResponse(ApiResponseBase):
    def response(self) -> JSONResponse:
        return JSONResponse(status_code = self.status_code, content = self.to_dict())
