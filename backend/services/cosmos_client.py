from enum import Enum
from typing import List, TypeVar, Dict, Any, Optional, Tuple, cast
from azure.cosmos.aio import CosmosClient, ContainerProxy, DatabaseProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from config import (
    AZURE_COSMOSDB_ENDPOINT,
    AZURE_COSMOSDB_PRIMARY_KEY,
    AZURE_COSMOSDB_NAME,
    AZURE_COSMOSDB_SESSION_CONTAINER_NAME,
    AZURE_COSMOSDB_CONVERSATION_CONTAINER_NAME,
    AZURE_COSMOSDB_PARTITION_KEY,


)
from services.telemetry_client import telemetry_client

T = TypeVar('T')

class ContainerType(Enum):
    SESSION = "session"
    CONVERSATION = "conversation_history"
    

class CosmosClientService:
    def __init__(self):
        if not all([AZURE_COSMOSDB_ENDPOINT, AZURE_COSMOSDB_PRIMARY_KEY, AZURE_COSMOSDB_NAME,
                   AZURE_COSMOSDB_SESSION_CONTAINER_NAME, AZURE_COSMOSDB_CONVERSATION_CONTAINER_NAME,
                   AZURE_COSMOSDB_PARTITION_KEY
                   ]):  # Add this
            raise ValueError("Missing required Cosmos DB configuration")

        self.endpoint_uri = cast(str, AZURE_COSMOSDB_ENDPOINT)
        self.primary_key = cast(str, AZURE_COSMOSDB_PRIMARY_KEY)
        self.database_id = cast(str, AZURE_COSMOSDB_NAME)
        self.container_ids = {
            ContainerType.SESSION: cast(str, AZURE_COSMOSDB_SESSION_CONTAINER_NAME),
            ContainerType.CONVERSATION: cast(str, AZURE_COSMOSDB_CONVERSATION_CONTAINER_NAME),

        }

        self.COSMOS_PAGE_SIZE = 50
        self.partition_key = cast(str, AZURE_COSMOSDB_PARTITION_KEY)
        self.cosmos_client = CosmosClient(self.endpoint_uri, self.primary_key)
        self.database: Optional[DatabaseProxy] = None
        self.containers: Dict[ContainerType, ContainerProxy] = {}
        telemetry_client.log_info("CosmosDB client service initialized")

    async def _initialize_cosmos_client(self):
        """Initialize database and containers if not already initialized."""
        try:
            if not self.database:
                telemetry_client.log_info("Creating/fetching database", {"database_id": self.database_id})
                await self.create_database(self.database_id)

            for container_type, container_id in self.container_ids.items():
                if container_type not in self.containers:
                    telemetry_client.log_info(f"Creating/fetching container", {
                        "container_type": container_type.value,
                        "container_id": container_id
                    })
                    await self.create_container(container_type, container_id, self.partition_key)
        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": "Failed to initialize cosmos client",
                "database_id": self.database_id
            })
            raise

    async def create_database(self, database_id: str):
        """Create database if it doesn't exist."""
        try:
            self.database = await self.cosmos_client.create_database_if_not_exists(database_id)
            telemetry_client.log_info("Database created/fetched successfully", {"database_id": database_id})
        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": "Failed to create database",
                "database_id": database_id
            })
            raise Exception(f'Error while creating database: {e}')

    async def create_container(self, container_type: ContainerType, container_id: str, partition_key: str):
        """Create container if it doesn't exist."""
        try:
            if not self.database:
                telemetry_client.log_info("Database not initialized, initializing first", {"database_id": self.database_id})
                await self.create_database(self.database_id)

            container = await self.database.create_container_if_not_exists(
                id = container_id,
                partition_key = partition_key
            )
            self.containers[container_type] = container
            telemetry_client.log_info("Container created/fetched successfully", {
                "container_type": container_type.value,
                "container_id": container_id
            })
        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": "Failed to create container",
                "container_type": container_type.value,
                "container_id": container_id
            })
            raise Exception(f'Error while creating container: {e}')

    async def get_container(self, container_type: ContainerType) -> ContainerProxy:
        """Get a container, initializing if necessary."""
        try:
            if container_type not in self.containers:
                telemetry_client.log_info("Container not initialized, initializing first", {
                    "container_type": container_type.value
                })
                await self._initialize_cosmos_client()

            container = self.containers.get(container_type)
            if not container:
                raise Exception(f"Container {container_type.value} not found")
            return container
        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": "Failed to get container",
                "container_type": container_type.value
            })
            raise

    async def read_item(self, container_type: ContainerType, id: str, partition_key: str) -> Optional[T]:
        try:
            container = await self.get_container(container_type)
            response = await container.read_item(item=id, partition_key=partition_key)
            telemetry_client.log_info("Item read successfully", {
                "container_type": container_type.value,
                "id": id,
                "partition_key": partition_key
            })
            return response
        except CosmosResourceNotFoundError:
            telemetry_client.log_info("Item not found", {
                "container_type": container_type.value,
                "id": id,
                "partition_key": partition_key
            })
            return None
        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": "Failed to read item",
                "container_type": container_type.value,
                "id": id,
                "partition_key": partition_key
            })
            return None

    async def save_item(self, container_type: ContainerType, item: dict, partition_key: str) -> bool:
        try:
            container = await self.get_container(container_type)
            
            partition_key_name = self.partition_key.lstrip('/')
            if partition_key_name not in item:
                item[partition_key_name] = partition_key
                
            if 'id' not in item:
                item['id'] = partition_key

            telemetry_client.log_info("Saving item", {
                "container_type": container_type.value,
                "id": item.get('id'),
                "partition_key": partition_key
            })
                
            await container.upsert_item(item)
            telemetry_client.log_info("Item saved successfully", {
                "container_type": container_type.value,
                "id": item.get('id'),
                "partition_key": partition_key
            })
            return True
        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": "Failed to save item",
                "container_type": container_type.value,
                "partition_key": partition_key
            })
            return False

    async def delete_item(self, container_type: ContainerType, id: str, partition_key: str) -> bool:
        try:
            container = await self.get_container(container_type)
            await container.delete_item(item=id, partition_key=partition_key)
            telemetry_client.log_info("Item deleted successfully", {
                "container_type": container_type.value,
                "id": id,
                "partition_key": partition_key
            })
            return True
        except CosmosResourceNotFoundError:
            telemetry_client.log_info("Item not found for deletion", {
                "container_type": container_type.value,
                "id": id,
                "partition_key": partition_key
            })
            return False
        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": "Failed to delete item",
                "container_type": container_type.value,
                "id": id,
                "partition_key": partition_key
            })
            return False

    async def find_items_by_filter(self, container_type: ContainerType, filters: Dict[str, Any]) -> List[T]:
        try:
            container = await self.get_container(container_type)
            
            if not filters:
                query = "SELECT * FROM c"
                parameters = []
            else:
                where_clauses = []
                parameters = []
                for idx, (key, value) in enumerate(filters.items()):
                    param_name = f"@param{idx}"
                    where_clauses.append(f"c.{key} = {param_name}")
                    parameters.append({"name": param_name, "value": value})
                where_str = " AND ".join(where_clauses)
                query = f"SELECT * FROM c WHERE {where_str}"

            telemetry_client.log_info("Executing query", {
                "container_type": container_type.value,
                "filter_count": len(filters),
                "query": query
            })

            items = container.query_items(
                query=query,
                parameters=parameters
            )
            results = [item async for item in items]
            telemetry_client.log_info("Query executed successfully", {
                "container_type": container_type.value,
                "filter_count": len(filters),
                "result_count": len(results)
            })
            return results
        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": "Failed to find items",
                "container_type": container_type.value,
                "filter_count": len(filters)
            })
            return []

    async def get_all_items(
        self,
        container_type: ContainerType,
        sort_field: Optional[str] = None,
        sort_order: str = "ASC",
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[T], Optional[str]]:
        try:
            container = await self.get_container(container_type)
            where_clauses = []
            parameters = []

            if filters:
                for idx, (key, value) in enumerate(filters.items()):
                    param_name = f"@param{idx}"
                    where_clauses.append(f"c.{key} = {param_name}")
                    parameters.append({"name": param_name, "value": value})

            query = "SELECT * FROM c"
            if where_clauses:
                where_str = " AND ".join(where_clauses)
                query += f" WHERE {where_str}"

            if sort_field:
                allowed_orders = ["ASC", "DESC"]
                order = sort_order.upper() if sort_order.upper() in allowed_orders else "ASC"
                if not sort_field.replace("_", "").isalnum():
                    raise ValueError("Invalid sort field")
                query += f" ORDER BY c.{sort_field} {order}"

            telemetry_client.log_info("Executing paginated query", {
                "container_type": container_type.value,
                "filter_count": len(filters) if filters else 0,
                "offset": offset,
                "limit": limit,
                "query": query
            })

            query_iterator = container.query_items(
                query=query,
                parameters=parameters,
                max_item_count=self.COSMOS_PAGE_SIZE
            ).by_page()

            results = []
            items_skipped = 0
            continuation_token = None

            async for page in query_iterator:
                page_items = [item async for item in page]
                
                if offset and items_skipped + len(page_items) < offset:
                    items_skipped += len(page_items)
                    continue

                start_index = max(0, offset - items_skipped) if offset else 0
                end_index = start_index + limit if limit else len(page_items)
                results.extend(page_items[start_index:end_index])

                if limit and len(results) >= limit:
                    continuation_token = query_iterator.continuation_token
                    break

                items_skipped += len(page_items)
                continuation_token = query_iterator.continuation_token

            final_results = results[:limit] if limit is not None else results
            telemetry_client.log_info("Paginated query executed successfully", {
                "container_type": container_type.value,
                "filter_count": len(filters) if filters else 0,
                "result_count": len(final_results),
                "has_more": continuation_token is not None,
                "offset": offset,
                "limit": limit
            })
            return final_results, continuation_token

        except Exception as e:
            telemetry_client.log_exception(e, {
                "error": "Failed to get all items",
                "container_type": container_type.value,
                "filter_count": len(filters) if filters else 0,
                "offset": offset,
                "limit": limit
            })
            return [], None

cosmos_client_singleton_instance = CosmosClientService()