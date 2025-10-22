import logging
import requests
from typing import Dict, Any
import sys
import os

# Add the parent directory to the path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config


class CurrencyExchangeRateService:
    """Service to fetch currency exchange rates from external API."""
    
    def __init__(self):
        """Initialize the service with API URL from config."""
        self.logger = logging.getLogger(__name__)
        self.api_url = config.get_currency_rate_api()
        self.timeout = 30  # seconds
        
        if not self.api_url:
            raise ValueError("Currency API URL not configured")
    
    def get_rates(self) -> Dict[str, Any]:
        """
        Fetch current currency exchange rates using the configured API URL.
        
        Returns:
            Dict: Complete JSON response from the currency API
            
        Raises:
            requests.RequestException: If the API request fails
            ValueError: If response is invalid
        """
        try:
            self.logger.info(f"Fetching currency rates from: {self.api_url}")
            
            # Make the GET request
            response = requests.get(self.api_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Get the JSON response
            rate_data = response.json()
            
            self.logger.info("Successfully fetched currency rates")
            return rate_data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching currency rates: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            raise


# Create a global service instance
currency_service = CurrencyExchangeRateService()