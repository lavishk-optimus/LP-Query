import logging
from typing import Dict, Any
import sys
import os

# Add the parent directory to the path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cosmos_service import cosmos_service
from services.currency_exchange_rate_service import currency_service


def update_exchange_rates() -> Dict[str, Any]:
    """
    Update currency exchange rates in Cosmos DB.
    
    This function:
    1. Fetches latest currency rates from external API
    2. Updates Cosmos DB with the new rates
    3. Returns the updated data or raises exceptions
    
    Returns:
        Dict[str, Any]: The updated item data from Cosmos DB
        
    Raises:
        ValueError: If configuration or validation errors occur
        Exception: If any step in the process fails
    """
    logging.info('Starting currency exchange rates update')
    
    try:
        # Update rates in Cosmos DB using the cosmos service
        # This internally calls the currency exchange rate service
        updated_item = cosmos_service.update_rates_in_cosmos()
        
        logging.info(f"Successfully updated currency rates. Item ID: {updated_item.get('id')}")
        logging.info(f"Last update: {updated_item.get('time_last_update_utc', 'Unknown')}")
        logging.info(f"Total currencies: {len(updated_item.get('conversion_rates', {}))}")
        
        return updated_item
        
    except ValueError as e:
        logging.error(f"Configuration or validation error: {str(e)}")
        raise
        
    except Exception as e:
        logging.error(f"Error updating currency rates: {str(e)}")
        raise