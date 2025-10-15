import logging
import uuid
from typing import Dict, Any, List
from azure.cosmos import CosmosClient, ContainerProxy, DatabaseProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError, CosmosHttpResponseError
import sys
import os

# Add the parent directory to the path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from services.currency_exchange_rate_service import currency_service


class CosmosService:
    """Service to interact with Azure Cosmos DB for currency rate data."""
    
    def __init__(self):
        """Initialize the Cosmos DB service with credentials from config."""
        self.logger = logging.getLogger(__name__)
        
        # Get configuration from config file
        self.endpoint = config.COSMOS_ENDPOINT
        self.key = config.COSMOS_KEY
        self.database_name = config.COSMOS_DATABASE_NAME
        self.container_name = config.CURRENCY_RATE_CONTAINER
        
        # Validate configuration
        if not all([self.endpoint, self.key, self.database_name, self.container_name]):
            raise ValueError("Missing required Cosmos DB configuration")
        
        # Initialize Cosmos client
        self.client = CosmosClient(self.endpoint, self.key)
        self.database: DatabaseProxy = None
        self.container: ContainerProxy = None
        
        self._initialize_database_and_container()
    
    def _initialize_database_and_container(self):
        """Initialize database and container references."""
        try:
            # Get database reference
            self.database = self.client.get_database_client(self.database_name)
            
            # Get container reference
            self.container = self.database.get_container_client(self.container_name)
            
            self.logger.info(f"Successfully connected to Cosmos DB: {self.database_name}/{self.container_name}")
            
        except CosmosResourceNotFoundError as e:
            self.logger.error(f"Database or container not found: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error initializing Cosmos DB connection: {str(e)}")
            raise
    
    def _delete_all_items(self):
        """Delete all existing items in the container."""
        try:
            self.logger.info("Deleting all existing items from currency rates container")
            
            # Query all items to get their IDs and partition keys
            query = "SELECT c.id FROM c"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            # Delete each item
            deleted_count = 0
            for item in items:
                try:
                    self.container.delete_item(
                        item=item['id'],
                        partition_key=item['id']  # Assuming id is the partition key
                    )
                    deleted_count += 1
                except CosmosResourceNotFoundError:
                    # Item already deleted, continue
                    pass
                except Exception as e:
                    self.logger.warning(f"Error deleting item {item['id']}: {str(e)}")
            
            self.logger.info(f"Successfully deleted {deleted_count} items from container")
            
        except Exception as e:
            self.logger.error(f"Error deleting items from container: {str(e)}")
            raise
    
    def _prepare_item_for_cosmos(self, rate_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare the currency rate data for Cosmos DB storage.
        
        Args:
            rate_data: Raw data from currency exchange rate service
            
        Returns:
            Dict: Formatted item for Cosmos DB
        """
        # Extract only the required fields and add Cosmos DB required fields
        cosmos_item = {
            "id": str(uuid.uuid4()),  # Generate unique ID
            "time_last_update_unix": rate_data.get("time_last_update_unix"),
            "time_last_update_utc": rate_data.get("time_last_update_utc"),
            "time_next_update_unix": rate_data.get("time_next_update_unix"),
            "time_next_update_utc": rate_data.get("time_next_update_utc"),
            "base_code": rate_data.get("base_code"),
            "conversion_rates": rate_data.get("conversion_rates", {})
        }
        
        return cosmos_item
    
    def update_rates_in_cosmos(self) -> Dict[str, Any]:
        """
        Update currency rates in Cosmos DB.
        
        This method:
        1. Fetches current rates from the currency exchange rate service
        2. Deletes all existing items in the container
        3. Upserts the new rate data as a single item
        
        Returns:
            Dict: The upserted item data
            
        Raises:
            Exception: If any step in the process fails
        """
        try:
            self.logger.info("Starting currency rates update in Cosmos DB")
            
            # Step 1: Fetch current rates from currency service
            self.logger.info("Fetching current currency rates from external API")
            rate_data = currency_service.get_rates()
            
            if not rate_data or rate_data.get("result") != "success":
                raise ValueError("Failed to fetch valid currency rate data")
            
            # Step 2: Delete all existing items
            self._delete_all_items()
            
            # Step 3: Prepare item for Cosmos DB
            cosmos_item = self._prepare_item_for_cosmos(rate_data)
            
            # Step 4: Upsert the new item
            self.logger.info("Upserting new currency rate data to Cosmos DB")
            upserted_item = self.container.upsert_item(cosmos_item)
            
            self.logger.info(f"Successfully updated currency rates in Cosmos DB. Item ID: {upserted_item['id']}")
            self.logger.info(f"Last update: {upserted_item.get('time_last_update_utc', 'Unknown')}")
            
            return upserted_item
            
        except Exception as e:
            self.logger.error(f"Error updating currency rates in Cosmos DB: {str(e)}")
            raise


# Create a global service instance
cosmos_service = CosmosService()