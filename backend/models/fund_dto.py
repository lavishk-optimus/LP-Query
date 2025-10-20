from pydantic import BaseModel, Field
from typing import Optional


class FundResponseDTO(BaseModel):
    """
    Data Transfer Object for fund response data
    This DTO standardizes the format for sending fund data back to clients
    """
    id: str = Field(..., description="Unique identifier for the fund record")
    name: str = Field(..., description="Name of the private equity or venture fund")
    vintage: int = Field(..., description="Year the fund was launched")
    commitment: int = Field(..., description="Total committed capital by LP")
    paidIn: int = Field(..., description="Capital already invested or called")
    nav: int = Field(..., description="Current Net Asset Value")
    irrNet: float = Field(..., description="Annualized internal rate of return (in %)")
    dpi: float = Field(..., description="Distributions to Paid-In multiple")
    tvpi: float = Field(..., description="Total Value to Paid-In multiple")
    pmeDelta: float = Field(..., description="Public Market Equivalent variance vs benchmark index")
    unfunded: int = Field(..., description="Commitment – Paid-In")
    lastReported: str = Field(..., description="Date of latest performance report (YYYY-MM-DD format)")

    class Config:
        """Pydantic model configuration"""
        json_schema_extra = {
            "example": {
                "id": "fund-1",
                "name": "Harbor Growth Fund III",
                "vintage": 2017,
                "commitment": 5000000,
                "paidIn": 4250000,
                "nav": 6100000,
                "irrNet": 17.8,
                "dpi": 0.65,
                "tvpi": 1.60,
                "pmeDelta": 3.2,
                "unfunded": 750000,
                "lastReported": "2024-06-30"
            }
        }

    @staticmethod
    def from_fund_dict(fund_data: dict, cosmos_id: Optional[str] = None) -> 'FundResponseDTO':
        """
        Convert a fund dictionary (from cosmos or model) to FundResponseDTO format
        
        Args:
            fund_data (dict): Fund data dictionary with original field names
            cosmos_id (str, optional): Cosmos DB document ID to use as fund ID
            
        Returns:
            FundResponseDTO: Standardized fund response format
        """
        # Generate ID from cosmos_id or fund name
        fund_id = cosmos_id or fund_data.get('id', f"fund-{fund_data.get('fund_name', 'unknown').lower().replace(' ', '-')}")
        
        return FundResponseDTO(
            id=fund_id,
            name=fund_data.get('fund_name', ''),
            vintage=fund_data.get('vintage', 0),
            commitment=fund_data.get('commitment', 0),
            paidIn=fund_data.get('paid_in', 0),  # Map paid_in to paidIn
            nav=fund_data.get('nav', 0),
            irrNet=fund_data.get('net_irr', 0.0),  # Map net_irr to irrNet
            dpi=fund_data.get('dpi', 0.0),
            tvpi=fund_data.get('tvpi', 0.0),
            pmeDelta=fund_data.get('pme_vs_index', 0.0),  # Map pme_vs_index to pmeDelta
            unfunded=fund_data.get('unfunded', 0),
            lastReported=str(fund_data.get('last_reported', ''))  # Ensure string format
        )

    @staticmethod
    def from_fund_list(funds_data: list, with_cosmos_ids: bool = False) -> list['FundResponseDTO']:
        """
        Convert a list of fund dictionaries to FundResponseDTO format
        
        Args:
            funds_data (list): List of fund data dictionaries
            with_cosmos_ids (bool): Whether the dictionaries include cosmos 'id' field
            
        Returns:
            list[FundResponseDTO]: List of standardized fund response objects
        """
        dto_list = []
        for i, fund_data in enumerate(funds_data):
            # Use cosmos ID if available, otherwise generate from index and name
            cosmos_id = fund_data.get('id') if with_cosmos_ids else None
            if not cosmos_id:
                fund_name = fund_data.get('fund_name', f'fund-{i+1}')
                cosmos_id = f"fund-{i+1}-{fund_name.lower().replace(' ', '-').replace('/', '-')}"
            
            dto = FundResponseDTO.from_fund_dict(fund_data, cosmos_id)
            dto_list.append(dto)
        
        return dto_list