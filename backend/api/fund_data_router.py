from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging
from typing import List, Dict, Any, Optional
from statistics import mean

from services import CosmosService
from models import FundResponseDTO


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/fund-data", tags=["Fund Data"])

# Service instance
cosmos_service = CosmosService()


def _consolidate_funds_data(funds_dto: List[FundResponseDTO]) -> Dict[str, Any]:
    """
    Consolidate multiple fund DTOs into a single summary with averages and totals
    
    Args:
        funds_dto: List of FundResponseDTO objects
        
    Returns:
        Dict with consolidated fund metrics
    """
    if not funds_dto:
        return {
            "total_funds_count": 0,
            "consolidated_metrics": {},
            "fund_names": []
        }
    
    # Fields that should be summed (net values) - using DTO field names
    sum_fields = [
        'commitment', 'paidIn', 'nav', 'unfunded'
    ]
    
    # Fields that should be averaged (ratios and percentages) - using DTO field names
    avg_fields = [
        'irrNet', 'dpi', 'tvpi', 'pmeDelta'
    ]
    
    # Initialize consolidation data
    consolidated = {
        "total_funds_count": len(funds_dto),
        "fund_names": [fund.get('fundName', 'Unknown') for fund in funds_dto],
        "consolidated_metrics": {}
    }
    
    # Calculate sums
    for field in sum_fields:
        values = [fund.get(field, 0) for fund in funds_dto if fund.get(field) is not None]
        if values:
            # Convert to float for calculation, handle string values
            numeric_values = []
            for val in values:
                try:
                    numeric_values.append(float(val))
                except (ValueError, TypeError):
                    continue
            
            if numeric_values:
                consolidated["consolidated_metrics"][field] = {
                    "total": sum(numeric_values),
                    "count": len(numeric_values)
                }
            else:
                consolidated["consolidated_metrics"][field] = {
                    "total": 0,
                    "count": 0
                }
        else:
            consolidated["consolidated_metrics"][field] = {
                "total": 0,
                "count": 0
            }
    
    # Calculate averages
    for field in avg_fields:
        values = [fund.get(field, 0) for fund in funds_dto if fund.get(field) is not None]
        if values:
            # Convert to float for calculation
            numeric_values = []
            for val in values:
                try:
                    numeric_values.append(float(val))
                except (ValueError, TypeError):
                    continue
            
            if numeric_values:
                consolidated["consolidated_metrics"][field] = {
                    "average": mean(numeric_values),
                    "count": len(numeric_values),
                    "min": min(numeric_values),
                    "max": max(numeric_values)
                }
            else:
                consolidated["consolidated_metrics"][field] = {
                    "average": 0,
                    "count": 0,
                    "min": 0,
                    "max": 0
                }
        else:
            consolidated["consolidated_metrics"][field] = {
                "average": 0,
                "count": 0,
                "min": 0,
                "max": 0
            }
    
    return consolidated


@router.get("/user/latest")
async def get_latest_funds(user_id: str) -> JSONResponse:
    """
    Get latest fund data for a specific user
    
    Args:
        user_id: ID of the user
        
    Returns:
        JSONResponse with user's latest fund data
    """
    try:
        logger.info(f"Retrieving latest funds for user: {user_id}")
        
        funds_data = cosmos_service.get_user_latest_funds(user_id)
        
        # Convert to DTO format
        funds_dto = FundResponseDTO.from_fund_list(funds_data, with_cosmos_ids=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "user_id": user_id,
                "data_type": "latest",
                "funds_count": len(funds_dto),
                "funds": [fund.dict() for fund in funds_dto]
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving latest funds for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve latest funds: {str(e)}"
        )


@router.get("/user/second-latest")
async def get_second_latest_funds(user_id: str) -> JSONResponse:
    """
    Get second latest fund data for a specific user
    
    Args:
        user_id: ID of the user
        
    Returns:
        JSONResponse with user's second latest fund data
    """
    try:
        logger.info(f"Retrieving second latest funds for user: {user_id}")
        
        funds_data = cosmos_service.get_user_second_latest_funds(user_id)
        
        # Convert to DTO format
        funds_dto = FundResponseDTO.from_fund_list(funds_data, with_cosmos_ids=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "user_id": user_id,
                "data_type": "second_latest",
                "funds_count": len(funds_dto),
                "funds": [fund.dict() for fund in funds_dto]
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving second latest funds for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve second latest funds: {str(e)}"
        )


@router.get("/user/all-funds")
async def get_all_funds(user_id: str) -> JSONResponse:
    """
    Get all fund data for a specific user (no filtering by date)
    
    Args:
        user_id: ID of the user
        
    Returns:
        JSONResponse with all user's fund data
    """
    try:
        logger.info(f"Retrieving all funds for user: {user_id}")
        
        # Query all fund data directly from cosmos service
        # We'll need to use the fund container directly for this
        all_funds_query = "SELECT * FROM c WHERE c.user_id = @user_id"
        all_funds_parameters = [{"name": "@user_id", "value": user_id}]
        
        all_fund_data = list(cosmos_service.fund_container.query_items(
            query=all_funds_query,
            parameters=all_funds_parameters,
            enable_cross_partition_query=True
        ))
        
        # Convert to DTO format
        funds_dto = FundResponseDTO.from_fund_list(all_fund_data, with_cosmos_ids=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "user_id": user_id,
                "data_type": "all",
                "funds_count": len(funds_dto),
                "funds": [fund.dict() for fund in funds_dto]
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving all funds for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve all funds: {str(e)}"
        )





