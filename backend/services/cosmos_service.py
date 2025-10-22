from azure.cosmos import CosmosClient, DatabaseProxy, ContainerProxy
from azure.cosmos.exceptions import CosmosHttpResponseError
import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import date
from config import config
from models.fund import Fund


logger = logging.getLogger(__name__)


class CosmosService:
    """Service for managing Azure Cosmos DB operations"""
    
    def __init__(self):
        """Initialize the Cosmos DB service with credentials from config"""
        if not config.validate_cosmos_config():
            raise ValueError(
                "Azure Cosmos DB configuration is missing. "
                "Please set COSMOS_ENDPOINT and COSMOS_KEY environment variables."
            )
        
        try:
            # Initialize Cosmos client
            self.client = CosmosClient(
                url=config.COSMOS_ENDPOINT,
                credential=config.COSMOS_KEY
            )
            
            self.database_name = config.COSMOS_DATABASE_NAME
            self.fund_container_name = config.COSMOS_FUND_CONTAINER
            self.latest_fund_mapping_container_name = config.COSMOS_LATEST_FUND_MAPPING_CONTAINER
            
            # Ensure database exists
            self.database = self._ensure_database_exists()
            
            # Ensure containers exist
            self.fund_container = self._ensure_container_exists(
                self.fund_container_name, 
                partition_key="/user_id"
            )
            self.latest_fund_mapping_container = self._ensure_container_exists(
                self.latest_fund_mapping_container_name, 
                partition_key="/user_id"
            )
            
            logger.info(
                f"CosmosService initialized successfully for database: {self.database_name}, "
                f"containers: {self.fund_container_name}, {self.latest_fund_mapping_container_name}"
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize CosmosService: {str(e)}")
            raise
    
    def _normalize_date(self, date_value) -> str:
        """
        Normalize date value to string format for comparison
        Database stores dates in YYYY-MM-DD format
        
        Args:
            date_value: Date in various formats (string, date object, etc.)
            
        Returns:
            str: Normalized date string in YYYY-MM-DD format
        """
        if not date_value:
            return ""
        
        if isinstance(date_value, str):
            # Handle ISO datetime format (2025-06-30T00:00:00 -> 2025-06-30)
            if 'T' in date_value:
                return date_value.split('T')[0]
            # Already in YYYY-MM-DD format
            else:
                return date_value
        else:
            # Handle date objects - convert to YYYY-MM-DD format
            return date_value.isoformat() if hasattr(date_value, 'isoformat') else str(date_value)
    
    def _ensure_database_exists(self) -> DatabaseProxy:
        """
        Ensure the database exists, create if it doesn't
        
        Returns:
            DatabaseProxy: Database client
        """
        try:
            # Try to get the database
            database = self.client.get_database_client(self.database_name)
            
            # Test if database exists by trying to read its properties
            database.read()
            logger.info(f"Database '{self.database_name}' already exists")
            return database
            
        except CosmosHttpResponseError as e:
            if e.status_code == 404:
                # Database doesn't exist, create it
                logger.info(f"Database '{self.database_name}' not found, creating...")
                try:
                    database = self.client.create_database(self.database_name)
                    logger.info(f"Database '{self.database_name}' created successfully")
                    return database
                except Exception as create_error:
                    logger.error(f"Failed to create database '{self.database_name}': {str(create_error)}")
                    raise
            else:
                logger.error(f"Error accessing database '{self.database_name}': {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error ensuring database exists: {str(e)}")
            raise
    
    def _ensure_container_exists(self, container_name: str, partition_key: str) -> ContainerProxy:
        """
        Ensure the container exists, create if it doesn't
        
        Args:
            container_name (str): Name of the container
            partition_key (str): Partition key for the container (e.g., "/user_id")
            
        Returns:
            ContainerProxy: Container client
        """
        try:
            # Try to get the container
            container = self.database.get_container_client(container_name)
            
            # Test if container exists by trying to read its properties
            container.read()
            logger.info(f"Container '{container_name}' already exists")
            return container
            
        except CosmosHttpResponseError as e:
            if e.status_code == 404:
                # Container doesn't exist, create it
                logger.info(f"Container '{container_name}' not found, creating with partition key '{partition_key}'...")
                try:
                    container = self.database.create_container(
                        id=container_name,
                        partition_key=partition_key,
                        offer_throughput=400  # Minimum throughput for development
                    )
                    logger.info(f"Container '{container_name}' created successfully with partition key '{partition_key}'")
                    return container
                except Exception as create_error:
                    logger.error(f"Failed to create container '{container_name}': {str(create_error)}")
                    raise
            else:
                logger.error(f"Error accessing container '{container_name}': {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error ensuring container exists: {str(e)}")
            raise
    
    def get_user_latest_funds(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Fetch the latest fund data for a given user by:
        1. Getting all fund mappings for the user from COSMOS_LATEST_FUND_MAPPING_CONTAINER
        2. For each mapping, fetching the corresponding fund data from COSMOS_FUND_CONTAINER
           where the last_reported date matches the last_reported date from the mapping
        
        Args:
            user_id (str): ID of the user to fetch latest funds for
            
        Returns:
            List[Dict[str, Any]]: List of latest fund data for the user
        """
        try:
            # Step 1: Get all fund mappings for the user from latest_fund_mapping container
            mapping_query = "SELECT * FROM c WHERE c.user_id = @user_id"
            mapping_parameters = [{"name": "@user_id", "value": user_id}]
            
            fund_mappings = list(self.latest_fund_mapping_container.query_items(
                query=mapping_query,
                parameters=mapping_parameters,
                enable_cross_partition_query=True
            ))
            
            if not fund_mappings:
                logger.info(f"No fund mappings found for user_id: {user_id}")
                return []
            
            logger.info(f"Found {len(fund_mappings)} fund mappings for user_id: {user_id}")
            
            # Step 2: Fetch ALL fund data for the user at once
            all_funds_query = "SELECT * FROM c WHERE c.user_id = @user_id"
            all_funds_parameters = [{"name": "@user_id", "value": user_id}]
            
            all_fund_data = list(self.fund_container.query_items(
                query=all_funds_query,
                parameters=all_funds_parameters,
                enable_cross_partition_query=True
            ))
            
            logger.info(f"Retrieved {len(all_fund_data)} total fund records for user_id: {user_id}")
            
            # Step 3: Filter fund data in memory based on mappings
            latest_funds = []
            
            for mapping in fund_mappings:
                fund_name = mapping.get('fund_name')
                last_reported = mapping.get('last_reported')
                
                if not fund_name or not last_reported:
                    logger.warning(f"Skipping mapping with missing fund_name or last_reported: {mapping.get('id', 'unknown')}")
                    continue
                
                # Convert string date to proper format if needed
                if isinstance(last_reported, str):
                    try:
                        # Handle both date string formats
                        if 'T' in last_reported:
                            last_reported_date = last_reported.split('T')[0]
                        else:
                            last_reported_date = last_reported
                    except Exception:
                        logger.warning(f"Invalid date format in mapping {mapping.get('id', 'unknown')}: {last_reported}")
                        continue
                else:
                    last_reported_date = last_reported.isoformat() if hasattr(last_reported, 'isoformat') else str(last_reported)
                
                # Filter from the already fetched fund data
                matching_funds = [
                    fund for fund in all_fund_data
                    if (fund.get('fund_name') == fund_name and 
                        self._normalize_date(fund.get('last_reported')) == last_reported_date)
                ]
                
                if matching_funds:
                    # Add the first (and should be only) matching fund data
                    latest_funds.append(matching_funds[0])
                    logger.info(f"Found fund data for {fund_name} with date {last_reported_date}")
                else:
                    logger.warning(f"No fund data found for {fund_name} with date {last_reported_date}")
            
            logger.info(f"Successfully retrieved {len(latest_funds)} latest funds for user_id: {user_id}")
            return latest_funds
            
        except CosmosHttpResponseError as e:
            logger.error(f"Cosmos error while fetching latest funds for user_id {user_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching latest funds for user_id {user_id}: {str(e)}")
            raise
    
    def get_user_second_latest_funds(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Fetch the second latest fund data for a given user by:
        1. Getting all fund data for the user from COSMOS_FUND_CONTAINER
        2. Grouping by fund_name and sorting by last_reported date
        3. For each fund, selecting the second most recent entry
        
        Args:
            user_id (str): ID of the user to fetch second latest funds for
            
        Returns:
            List[Dict[str, Any]]: List of second latest fund data for the user
        """
        try:
            # Step 1: Fetch ALL fund data for the user
            all_funds_query = "SELECT * FROM c WHERE c.user_id = @user_id"
            all_funds_parameters = [{"name": "@user_id", "value": user_id}]
            
            all_fund_data = list(self.fund_container.query_items(
                query=all_funds_query,
                parameters=all_funds_parameters,
                enable_cross_partition_query=True
            ))
            
            if not all_fund_data:
                logger.info(f"No fund data found for user_id: {user_id}")
                return []
                
            logger.info(f"Retrieved {len(all_fund_data)} total fund records for user_id: {user_id}")
            
            # Step 2: Group funds by fund_name and sort by last_reported date
            fund_groups = {}
            
            for fund in all_fund_data:
                fund_name = fund.get('fund_name')
                last_reported = fund.get('last_reported')
                
                if not fund_name or not last_reported:
                    logger.warning(f"Skipping fund with missing fund_name or last_reported: {fund.get('id', 'unknown')}")
                    continue
                
                # Normalize the date for consistent comparison
                normalized_date = self._normalize_date(last_reported)
                
                if fund_name not in fund_groups:
                    fund_groups[fund_name] = []
                
                fund_groups[fund_name].append({
                    'fund_data': fund,
                    'normalized_date': normalized_date
                })
            
            # Step 3: For each fund group, find the second latest entry
            second_latest_funds = []
            
            for fund_name, fund_list in fund_groups.items():
                # Sort by date in descending order (latest first)
                fund_list.sort(key=lambda x: x['normalized_date'], reverse=True)
                
                if len(fund_list) >= 2:
                    # Get the second latest (index 1)
                    second_latest_fund = fund_list[1]['fund_data']
                    second_latest_funds.append(second_latest_fund)
                    logger.info(f"Found second latest data for {fund_name} with date {fund_list[1]['normalized_date']}")
                else:
                    logger.info(f"Fund {fund_name} has only {len(fund_list)} record(s), no second latest available")
            
            logger.info(f"Successfully retrieved {len(second_latest_funds)} second latest funds for user_id: {user_id}")
            return second_latest_funds
            
        except CosmosHttpResponseError as e:
            logger.error(f"Cosmos error while fetching second latest funds for user_id {user_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching second latest funds for user_id {user_id}: {str(e)}")
            raise
    
    def upload_fund_data(self, fund: Fund) -> Optional[Dict[str, Any]]:
        """
        Upload fund data to the funds container with mapping comparison logic:
        1. Check if mapping exists for user_id and fund_name
        2. If mapping exists, compare dates:
           - If fund's last_reported date is later than mapping's last_reported: update mapping and upload fund
           - If fund's last_reported date is same or earlier: skip upload
        3. If mapping doesn't exist: create mapping and upload fund
        
        Args:
            fund (Fund): Fund object to upload
            
        Returns:
            Optional[Dict[str, Any]]: Created fund item with metadata, or None if skipped
        """
        try:
            user_id = fund.user_id
            fund_name = fund.fund_name
            fund_last_reported = self._normalize_date(fund.last_reported)
            
            # Step 1: Check if mapping exists for user_id and fund_name
            search_query = "SELECT * FROM c WHERE c.user_id = @user_id AND c.fund_name = @fund_name"
            search_parameters = [
                {"name": "@user_id", "value": user_id},
                {"name": "@fund_name", "value": fund_name}
            ]
            
            existing_mappings = list(self.latest_fund_mapping_container.query_items(
                query=search_query,
                parameters=search_parameters,
                enable_cross_partition_query=True
            ))
            
            if existing_mappings:
                # Step 2: Mapping exists, compare dates
                existing_mapping = existing_mappings[0]
                mapping_last_reported = self._normalize_date(existing_mapping.get('last_reported'))
                
                logger.info(f"Found existing mapping for user: {user_id}, fund: {fund_name}")
                logger.info(f"Fund last_reported: {fund_last_reported}, Mapping last_reported: {mapping_last_reported}")
                
                # Compare dates (fund_last_reported should be later than mapping_last_reported to proceed)
                if fund_last_reported <= mapping_last_reported:
                    logger.info(f"Skipping upload - fund date {fund_last_reported} is not later than mapping date {mapping_last_reported}")
                    return None
                
                # Fund date is later, update mapping
                existing_mapping['last_reported'] = fund_last_reported
                self.latest_fund_mapping_container.replace_item(
                    item=existing_mapping['id'], 
                    body=existing_mapping
                )
                logger.info(f"Updated mapping last_reported to: {fund_last_reported}")
                
            else:
                # Step 3: No mapping exists, create new mapping
                new_mapping = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "fund_name": fund_name,
                    "last_reported": fund_last_reported
                }
                
                self.latest_fund_mapping_container.create_item(body=new_mapping)
                logger.info(f"Created new mapping for user: {user_id}, fund: {fund_name}, date: {fund_last_reported}")
            
            # Step 4: Upload fund data to funds container
            # Use model_dump with mode='json' to ensure proper serialization
            fund_data = fund.model_dump(mode='json')
            
            # Add required 'id' field for Cosmos DB (generate unique ID)
            fund_data['id'] = str(uuid.uuid4())
            
            created_item = self.fund_container.create_item(body=fund_data)
            
            logger.info(f"Successfully uploaded fund data for user: {user_id}, fund: {fund_name}, date: {fund_last_reported}")
            return created_item
            
        except CosmosHttpResponseError as e:
            logger.error(f"Cosmos error while uploading fund data for user {user_id}, fund {fund_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while uploading fund data for user {user_id}, fund {fund_name}: {str(e)}")
            raise
    
    def upload_multiple_funds(self, funds: List[Fund], user_id: str) -> Dict[str, Any]:
        """
        Upload multiple fund data items for a user. Uses upload_fund_data for each fund
        which includes mapping comparison logic.
        
        Args:
            funds (List[Fund]): List of Fund objects to upload
            user_id (str): ID of the user (for validation and logging)
            
        Returns:
            Dict[str, Any]: Summary of upload results including counts and details
        """
        try:
            upload_results = {
                "total_funds": len(funds),
                "uploaded_count": 0,
                "skipped_count": 0,
                "error_count": 0,
                "uploaded_funds": [],
                "skipped_funds": [],
                "error_funds": []
            }
            
            logger.info(f"Starting upload of {len(funds)} funds for user: {user_id}")
            
            for i, fund in enumerate(funds):
                try:
                    # Validate that fund belongs to the specified user
                    if fund.user_id != user_id:
                        logger.warning(f"Fund {fund.fund_name} belongs to user {fund.user_id}, not {user_id}. Skipping.")
                        upload_results["skipped_count"] += 1
                        upload_results["skipped_funds"].append({
                            "fund_name": fund.fund_name,
                            "reason": f"User ID mismatch: {fund.user_id} != {user_id}"
                        })
                        continue
                    
                    # Upload the fund using existing upload_fund_data method
                    result = self.upload_fund_data(fund)
                    
                    if result:
                        # Upload was successful
                        upload_results["uploaded_count"] += 1
                        upload_results["uploaded_funds"].append({
                            "fund_name": fund.fund_name,
                            "last_reported": self._normalize_date(fund.last_reported),
                            "cosmos_id": result.get("id")
                        })
                        logger.info(f"Progress: {i+1}/{len(funds)} - Uploaded {fund.fund_name}")
                    else:
                        # Upload was skipped (not newer than existing)
                        upload_results["skipped_count"] += 1
                        upload_results["skipped_funds"].append({
                            "fund_name": fund.fund_name,
                            "reason": "Fund data is not newer than existing mapping"
                        })
                        logger.info(f"Progress: {i+1}/{len(funds)} - Skipped {fund.fund_name}")
                        
                except Exception as fund_error:
                    # Individual fund upload failed
                    upload_results["error_count"] += 1
                    upload_results["error_funds"].append({
                        "fund_name": getattr(fund, 'fund_name', 'unknown'),
                        "error": str(fund_error)
                    })
                    logger.error(f"Error uploading fund {getattr(fund, 'fund_name', 'unknown')}: {str(fund_error)}")
                    continue
            
            # Log final summary
            logger.info(
                f"Upload completed for user {user_id}. "
                f"Uploaded: {upload_results['uploaded_count']}, "
                f"Skipped: {upload_results['skipped_count']}, "
                f"Errors: {upload_results['error_count']}"
            )
            
            return upload_results
            
        except Exception as e:
            logger.error(f"Unexpected error during bulk upload for user {user_id}: {str(e)}")
            raise
    
    def update_or_create_fund_mapping(self, user_id: str, fund_name: str, last_reported_date: str) -> Dict[str, Any]:
        """
        Update or create fund mapping entry in the mapping container.
        If an entry exists for the user_id and fund_name, update the last_reported date.
        If no entry exists, create a new one.
        
        Args:
            user_id (str): ID of the user
            fund_name (str): Name of the fund
            last_reported_date (str): Date when the fund was last reported (YYYY-MM-DD format)
            
        Returns:
            Dict[str, Any]: Updated or created mapping item
        """
        try:
            # First, try to find existing mapping
            search_query = "SELECT * FROM c WHERE c.user_id = @user_id AND c.fund_name = @fund_name"
            search_parameters = [
                {"name": "@user_id", "value": user_id},
                {"name": "@fund_name", "value": fund_name}
            ]
            
            existing_mappings = list(self.latest_fund_mapping_container.query_items(
                query=search_query,
                parameters=search_parameters,
                enable_cross_partition_query=True
            ))
            
            if existing_mappings:
                # Update existing mapping
                existing_mapping = existing_mappings[0]
                existing_mapping['last_reported'] = last_reported_date
                
                updated_item = self.latest_fund_mapping_container.replace_item(
                    item=existing_mapping['id'], 
                    body=existing_mapping
                )
                
                logger.info(f"Updated existing fund mapping for user: {user_id}, fund: {fund_name}, date: {last_reported_date}")
                return updated_item
                
            else:
                # Create new mapping
                new_mapping = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "fund_name": fund_name,
                    "last_reported": last_reported_date
                }
                
                created_item = self.latest_fund_mapping_container.create_item(body=new_mapping)
                
                logger.info(f"Created new fund mapping for user: {user_id}, fund: {fund_name}, date: {last_reported_date}")
                return created_item
                
        except CosmosHttpResponseError as e:
            logger.error(f"Cosmos error while updating/creating fund mapping for user {user_id}, fund {fund_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while updating/creating fund mapping for user {user_id}, fund {fund_name}: {str(e)}")
            raise
