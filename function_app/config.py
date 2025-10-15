import os
from typing import Optional


class Config:
    """Configuration class to manage application settings."""
    
    # Cosmos DB Configuration
    COSMOS_ENDPOINT: str = os.getenv("COSMOS_ENDPOINT", "")
    COSMOS_KEY: str = os.getenv("COSMOS_KEY", "")
    COSMOS_DATABASE_NAME: str = os.getenv("COSMOS_DATABASE_NAME", "lp_query_db")
    
    # Container Names
    CURRENCY_RATE_CONTAINER: str = os.getenv("CURRENCY_RATE_CONTAINER", "currency_rates")
    
    # Application Settings
    APP_NAME: str = os.getenv("APP_NAME", "LP-Query")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Currency API Settings (if using external currency API)
    CURRENCY_API_KEY: Optional[str] = os.getenv("CURRENCY_API_KEY")
    CURRENCY_API_BASE_URL: str = os.getenv("CURRENCY_API_BASE_URL", "https://api.exchangerate-api.com/v4/latest")
    
    # Default Currency Settings
    DEFAULT_BASE_CURRENCY: str = os.getenv("DEFAULT_BASE_CURRENCY", "USD")
    SUPPORTED_CURRENCIES: list = [
        "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR", "KRW"
    ]
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate that required configuration values are present."""
        required_settings = [
            cls.COSMOS_ENDPOINT,
            cls.COSMOS_KEY,
            cls.COSMOS_DATABASE_NAME,
            cls.CURRENCY_RATE_CONTAINER,
            cls.CURRENCY_API_BASE_URL,
            cls.CURRENCY_API_KEY
        ]
        
        missing_settings = []
        for i, setting in enumerate(required_settings):
            setting_names = ["COSMOS_ENDPOINT", "COSMOS_KEY", "COSMOS_DATABASE_NAME"]
            if not setting:
                missing_settings.append(setting_names[i])
        
        if missing_settings:
            raise ValueError(f"Missing required configuration: {', '.join(missing_settings)}")
        
        return True
    
    @classmethod
    def get_cosmos_connection_string(cls) -> str:
        """Generate Cosmos DB connection string."""
        return f"AccountEndpoint={cls.COSMOS_ENDPOINT};AccountKey={cls.COSMOS_KEY};"
    
    
    
    @classmethod
    def is_supported_currency(cls, currency_code: str) -> bool:
        """Check if a currency code is supported."""
        return currency_code.upper() in cls.SUPPORTED_CURRENCIES
    
    @classmethod
    def get_all_settings(cls) -> dict:
        """Get all configuration settings as a dictionary."""
        return {
            "cosmos_endpoint": cls.COSMOS_ENDPOINT,
            "cosmos_database_name": cls.COSMOS_DATABASE_NAME,
            "currency_rate_container": cls.CURRENCY_RATE_CONTAINER,
            "app_name": cls.APP_NAME,
            "log_level": cls.LOG_LEVEL,
            "currency_api_base_url": cls.CURRENCY_API_BASE_URL,
            "default_base_currency": cls.DEFAULT_BASE_CURRENCY,
            "supported_currencies": cls.SUPPORTED_CURRENCIES
        }
    
    @classmethod
    def get_currency_rate_api(cls) -> str:
        """Get the currency API URL with key and base currency."""
        if not cls.CURRENCY_API_KEY:
            raise ValueError("CURRENCY_API_KEY is required")
        return f"{cls.CURRENCY_API_BASE_URL}{cls.CURRENCY_API_KEY}/latest/{cls.DEFAULT_BASE_CURRENCY}"


# Create a global config instance
config = Config()