import logging
from typing import Dict, Any
import sys
import os

# Add the parent directory to the path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cosmos_service import cosmos_service
from config import config


def exchange_currency(from_currency: str, to_currency: str, amount: float = 1.0) -> Dict[str, Any]:
    """
    Exchange currency from one currency to another using rates from Cosmos DB.
    
    Args:
        from_currency: Source currency code (e.g., "USD", "EUR")
        to_currency: Target currency code (e.g., "EUR", "JPY")
        amount: Amount to convert (default: 1.0)
        
    Returns:
        Dict containing exchange rate and conversion information including final converted amount
        
    Raises:
        ValueError: If currencies are not found, invalid, or amount is negative
        Exception: If unable to fetch rates from Cosmos DB
    """
    logging.info(f"Converting {amount} {from_currency} to {to_currency}")
    
    try:
        # Validate amount
        if amount < 0:
            raise ValueError("Amount must be non-negative")
        
        # Fetch current rates from Cosmos DB
        rate_data = cosmos_service.get_current_rates_from_cosmos()
        conversion_rates = rate_data.get("conversion_rates", {})
        
        # Normalize currency codes to uppercase
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        # Get supported currencies from config
        supported_currencies = config.SUPPORTED_CURRENCIES
        
        # First validate against supported currencies list from config
        if from_currency not in supported_currencies:
            raise ValueError(f"Currency '{from_currency}' is not supported. Supported currencies: {', '.join(supported_currencies)}")
        
        if to_currency not in supported_currencies:
            raise ValueError(f"Currency '{to_currency}' is not supported. Supported currencies: {', '.join(supported_currencies)}")
        
        # Then validate that both currencies exist in the conversion rates from Cosmos DB
        if from_currency not in conversion_rates:
            raise ValueError(f"Currency '{from_currency}' not found in current exchange rates from database")
        
        if to_currency not in conversion_rates:
            raise ValueError(f"Currency '{to_currency}' not found in current exchange rates from database")
        
        # Get the rates for both currencies (these are rates relative to base currency)
        from_rate = conversion_rates[from_currency]
        to_rate = conversion_rates[to_currency]
        
        # Calculate the exchange rate from source to target currency
        # Formula: (1 unit of from_currency) * (to_rate / from_rate) = units of to_currency
        exchange_rate = to_rate / from_rate
        
        # Calculate the final converted amount
        converted_amount = amount * exchange_rate
        
        # Prepare the response
        result = {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "original_amount": amount,
            "converted_amount": round(converted_amount, 5),
            "exchange_rate": exchange_rate,
            "base_currency": rate_data.get("base_code"),
            "last_update": rate_data.get("time_last_update_utc"),
            "conversion_summary": f"{amount} {from_currency} = {round(converted_amount, 2)} {to_currency}",
            "rate_info": {
                f"1 {from_currency}": f"{exchange_rate:.6f} {to_currency}",
                f"1 {to_currency}": f"{1/exchange_rate:.6f} {from_currency}"
            }
        }
        
        logging.info(f"Successfully calculated: {amount} {from_currency} = {converted_amount:.2f} {to_currency} (rate: {exchange_rate:.6f})")
        
        return result
        
    except ValueError as e:
        logging.error(f"Validation error in currency exchange: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error fetching exchange rates or calculating conversion: {str(e)}")
        raise


def convert_amount(amount: float, from_currency: str, to_currency: str) -> Dict[str, Any]:
    """
    Convert a specific amount from one currency to another.
    
    Args:
        amount: Amount to convert
        from_currency: Source currency code
        to_currency: Target currency code
        
    Returns:
        Dict containing conversion details
        
    Raises:
        ValueError: If amount is invalid or currencies not found
        Exception: If unable to fetch rates
    """
    logging.info(f"Converting {amount} {from_currency} to {to_currency}")
    
    try:
        # Validate amount
        if amount < 0:
            raise ValueError("Amount must be non-negative")
        
        # Get exchange rate
        exchange_info = exchange_currency(from_currency, to_currency)
        exchange_rate = exchange_info["exchange_rate"]
        
        # Calculate converted amount
        converted_amount = amount * exchange_rate
        
        # Prepare detailed response
        result = {
            "original_amount": amount,
            "from_currency": from_currency.upper(),
            "converted_amount": round(converted_amount, 2),
            "to_currency": to_currency.upper(),
            "exchange_rate": exchange_rate,
            "base_currency": exchange_info["base_currency"],
            "last_update": exchange_info["last_update"],
            "conversion_summary": f"{amount} {from_currency.upper()} = {round(converted_amount, 2)} {to_currency.upper()}"
        }
        
        logging.info(f"Successfully converted: {amount} {from_currency} = {converted_amount:.2f} {to_currency}")
        
        return result
        
    except ValueError as e:
        logging.error(f"Validation error in amount conversion: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error in amount conversion: {str(e)}")
        raise


def get_supported_currencies() -> Dict[str, Any]:
    """
    Get the list of supported currencies from config and available rates.
    
    Returns:
        Dict containing supported currencies information
    """
    logging.info("Fetching supported currencies information")
    
    try:
        # Get supported currencies from config
        config_supported = config.SUPPORTED_CURRENCIES
        
        # Get available currencies from Cosmos DB
        rate_data = cosmos_service.get_current_rates_from_cosmos()
        available_rates = list(rate_data.get("conversion_rates", {}).keys())
        
        # Find intersection of supported and available currencies
        available_supported = [currency for currency in config_supported if currency in available_rates]
        
        result = {
            "supported_currencies": config_supported,
            "available_in_database": available_rates,
            "supported_and_available": available_supported,
            "total_supported": len(config_supported),
            "total_available": len(available_rates),
            "base_currency": rate_data.get("base_code"),
            "last_update": rate_data.get("time_last_update_utc")
        }
        
        logging.info(f"Retrieved {len(config_supported)} supported currencies, {len(available_rates)} available in database")
        
        return result
        
    except Exception as e:
        logging.error(f"Error fetching supported currencies: {str(e)}")
        raise