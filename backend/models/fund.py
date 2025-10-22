from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


class Fund(BaseModel):
    """
    Model representing private equity or venture fund data
    """
    user_id: str = Field(..., description="ID of the user owning the fund data")
    fund_name: str = Field(..., description="Name of the private equity or venture fund")
    vintage: int = Field(..., description="Year the fund was launched", ge=1900, le=2100)
    commitment: int = Field(..., description="Total committed capital by LP", ge=0)
    paid_in: int = Field(..., description="Capital already invested or called", ge=0)
    nav: int = Field(..., description="Current Net Asset Value", ge=0)
    net_irr: float = Field(..., description="Annualized internal rate of return (in %)")
    dpi: float = Field(..., description="Distributions to Paid-In multiple", ge=0)
    tvpi: float = Field(..., description="Total Value to Paid-In multiple", ge=0)
    pme_vs_index: float = Field(..., description="Public Market Equivalent variance vs benchmark index")
    unfunded: int = Field(..., description="Commitment – Paid-In", ge=0)
    status: str = Field(..., description="Fund lifecycle stage")
    last_reported: date = Field(..., description="Date of latest performance report")

    class Config:
        """Pydantic model configuration"""
        use_enum_values = True
        json_encoders = {
            date: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "user_id": "user_12345",
                "fund_name": "Growth Capital Fund III",
                "vintage": 2020,
                "commitment": 50000000,
                "paid_in": 35000000,
                "nav": 42000000,
                "net_irr": 15.5,
                "dpi": 0.8,
                "tvpi": 1.2,
                "pme_vs_index": 1.15,
                "unfunded": 15000000,
                "status": "Active",
                "last_reported": "2024-12-31"
            }
        }

    def __str__(self) -> str:
        return f"{self.fund_name} ({self.vintage}) - {self.status}"


class FundUpdateDateMapping(BaseModel):
    """
    Model for tracking fund update dates by user and fund name
    """
    user_id: str = Field(..., description="ID of the user owning the fund data")
    fund_name: str = Field(..., description="Name of the private equity or venture fund")
    last_reported: date = Field(..., description="Date when the fund data was last reported")

    class Config:
        """Pydantic model configuration"""
        json_encoders = {
            date: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "user_id": "user_12345",
                "fund_name": "Growth Capital Fund III",
                "last_reported": "2024-12-31"
            }
        }

    def __str__(self) -> str:
        return f"{self.fund_name} - Last Reported: {self.last_reported}"







