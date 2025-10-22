import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for application settings"""
    
    # Azure Cosmos DB Configuration
    COSMOS_ENDPOINT: Optional[str] = os.getenv("COSMOS_ENDPOINT")
    COSMOS_KEY: Optional[str] = os.getenv("COSMOS_KEY")
    COSMOS_DATABASE_NAME: str = os.getenv("COSMOS_DATABASE_NAME", "lpquery")
    
    # Cosmos DB Containers
    COSMOS_FUND_CONTAINER: str = os.getenv("COSMOS_FUND_CONTAINER", "funds")
    COSMOS_LATEST_FUND_MAPPING_CONTAINER: str = os.getenv("COSMOS_LATEST_FUND_MAPPING_CONTAINER", "latest_fund_mapping")
    
    # Azure OpenAI Configuration (Azure AI Foundry)
    AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_KEY: Optional[str] = os.getenv("AZURE_OPENAI_KEY")
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")
    
    @classmethod
    def validate_cosmos_config(cls) -> bool:
        """Validate that required Cosmos DB configuration is present"""
        return bool(cls.COSMOS_ENDPOINT and cls.COSMOS_KEY)
    
    @classmethod
    def validate_azure_openai_config(cls) -> bool:
        """Validate that Azure OpenAI (Azure AI Foundry) configuration is present"""
        return bool(
            cls.AZURE_OPENAI_ENDPOINT and 
            cls.AZURE_OPENAI_KEY and 
            cls.AZURE_OPENAI_DEPLOYMENT_NAME
        )


# Create a global config instance
config = Config()