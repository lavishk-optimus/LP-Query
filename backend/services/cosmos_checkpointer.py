import base64
import json
import asyncio
from typing import Any, Dict, Iterator, AsyncIterator, Optional, Sequence, Tuple, List
from types import TracebackType
from abc import ABC, abstractmethod
from services.telemetry_client import telemetry_client
from azure.cosmos import PartitionKey, exceptions
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
    get_checkpoint_id,
    SerializerProtocol,
)

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from contextlib import AbstractAsyncContextManager

from langchain_core.runnables import RunnableConfig
from typing_extensions import Self

# Define constants for consistent key usage
CONFIGURABLE = 'configurable'
THREAD_ID = 'thread_id'
METADATA = 'metadata'
CHECKPOINT = 'checkpoint'
CHECKPOINT_ENCODED = 'checkpoint_encoded'
METADATA_ENCODED = 'metadata_encoded'

class BaseCosmosDBSaver(ABC, BaseCheckpointSaver):
    '''Abstract base class for CosmosDB Savers with shared logic.'''

    serde: SerializerProtocol
    
    DEFAULT_INDEXING_POLICY = {
        'indexingMode': 'consistent',
        'automatic': True,
        'includedPaths': [
            {
                'path': f'/{THREAD_ID}/?',
                'indexes': [
                    {
                        'kind': 'Range',
                        'dataType': 'String',
                        'precision': -1
                    },
                    {
                        'kind': 'Range',
                        'dataType': 'Number',
                        'precision': -1
                    }
                ]
            },
            
            {
                'path': '/*',
                'compositeIndexes': [
                    [
                        {'path': f'/{THREAD_ID}', 'order': 'ascending'}
                    ]
                ]
            }
        ],
        'excludedPaths': [
            {'path': '/_etag/?'},
        ]
    }

    def __init__(
        self,
        *,
        database_name: str,
        container_name: str,
        serde: Optional[SerializerProtocol] = None,
    ) -> None:
        super().__init__(serde=serde or JsonPlusSerializer())
        self.database_name = database_name
        self.container_name = container_name
        self.database = None
        self.container = None

    def setup(self) -> None:
        '''
        Set up the CosmosDB container with necessary configurations.

        This method can be overridden to include any initialization logic,
        such as creating stored procedures or defining indexing policies.
        '''
        pass
    
    def setup_indexing_policy(self) -> Dict[str, Any]:
        '''Returns the default indexing policy. Can be overridden by subclasses.'''
        return self.DEFAULT_INDEXING_POLICY
    
    @abstractmethod
    def upsert_item(self, doc: Dict[str, Any]) -> None:
        '''Abstract method to upsert an item into the database.'''
        pass
    
    @abstractmethod
    def upsert_items(self, docs: List[Dict[str, Any]]) -> None:
        '''Abstract method to upsert multiple items into the database.'''
        pass

    @abstractmethod
    def query_items(
        self,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        '''Abstract method to query items from the database.'''
        pass

    def _serialize_field(self, data: Any) -> Tuple[Any, bool]:
        '''Helper method to serialize and conditionally encode data.'''
        serialized = self.serde.dumps(data)
        encoded = False
        try:
            json.dumps(serialized)
            data_out = serialized
        except (TypeError, ValueError):
            if isinstance(serialized, str):
                serialized = serialized.encode('utf-8')
            data_out = base64.b64encode(serialized).decode('utf-8')
            encoded = True
        return data_out, encoded

    def _deserialize_field(self, doc: Dict[str, Any], field_name: str, encoded_flag_name: str) -> Any:
        '''Helper method to deserialize a field from the document.'''
        data = doc[field_name]
        encoded = doc.get(encoded_flag_name, False)
        if encoded:
            serialized = base64.b64decode(data.encode('utf-8'))
        else:
            serialized = data
            if isinstance(serialized, str):
                serialized = serialized.encode('utf-8')
        return self.serde.loads(serialized)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        '''
        Retrieve a checkpoint tuple from the database.

        Args:
            config (RunnableConfig): The runnable configuration containing 'thread_id' and optional 'checkpoint_id'.

        Returns:
            Optional[CheckpointTuple]: A CheckpointTuple if found, else None.

        Raises:
            ValueError: If 'thread_id' is not provided in the config.
        '''
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        if not thread_id:
            raise ValueError(f'"{THREAD_ID}" is required in config["{CONFIGURABLE}"]')
        checkpoint_id = get_checkpoint_id(config)
        parameters = [{'name': '@thread_id', 'value': thread_id}]
        if checkpoint_id:
            query = (
                'SELECT * FROM c WHERE c.thread_id = @thread_id AND IS_DEFINED(c.checkpoint) '
                'AND c.checkpoint_id = @checkpoint_id'
            )
            parameters.append({'name': '@checkpoint_id', 'value': checkpoint_id})
        else:
            query = (
                'SELECT * FROM c WHERE c.thread_id = @thread_id AND IS_DEFINED(c.checkpoint) '
                'ORDER BY c.checkpoint_id DESC OFFSET 0 LIMIT 1'
            )

        items = self.query_items(query=query, parameters=parameters)
        results = list(items)
        if results:
            doc = results[0]
            checkpoint = self._deserialize_field(doc, CHECKPOINT, CHECKPOINT_ENCODED)
            metadata = self._deserialize_field(doc, METADATA, METADATA_ENCODED)
            
            return CheckpointTuple(
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                    }
                },
                checkpoint,
                metadata,
            )
        else:
            return None

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        '''
        List checkpoints from the database.

        Args:
            config (Optional[RunnableConfig]): Optional runnable configuration.
            filter (Optional[Dict[str, Any]]): Optional filter for metadata.
            before (Optional[RunnableConfig]): Optional configuration to list checkpoints before a certain point.
            limit (Optional[int]): Optional limit on the number of checkpoints to return.

        Returns:
            Iterator[CheckpointTuple]: An iterator of CheckpointTuples.
        '''
        parameters = []
        conditions = []
        if config is not None:
            thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
            if not thread_id:
                raise ValueError(f'"{THREAD_ID}" is required in config["{CONFIGURABLE}"]')
            conditions.append('c.thread_id = @thread_id')
            parameters.append({'name': '@thread_id', 'value': thread_id})

        if filter:
            for key, value in filter.items():
                conditions.append(f'c.metadata.{key} = @{key}')
                parameters.append({'name': f'@{key}', 'value': value})

        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        limit_clause = f'OFFSET 0 LIMIT {limit}' if limit else ''

        query = f'SELECT * FROM c WHERE {where_clause} {limit_clause}'

        items = self.query_items(query=query, parameters=parameters)
        for doc in items:
            checkpoint = self._deserialize_field(doc, CHECKPOINT, CHECKPOINT_ENCODED)
            metadata = self._deserialize_field(doc, METADATA, METADATA_ENCODED)
            parent_config = (
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                    }
                }
            )
            yield CheckpointTuple(
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                    }
                },
                checkpoint,
                metadata,
                parent_config,
            )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        '''
        Save a checkpoint to the database.

        Args:
            config (RunnableConfig): The runnable configuration.
            checkpoint (Checkpoint): The checkpoint data to save.
            metadata (CheckpointMetadata): Metadata associated with the checkpoint.
            new_versions (ChannelVersions): New channel versions.

        Returns:
            RunnableConfig: Updated runnable configuration.

        Raises:
            ValueError: If required fields are missing in the config or checkpoint.
        '''
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        if not thread_id:
            raise ValueError(f'"{THREAD_ID}" is required in config["{CONFIGURABLE}"]')
        checkpoint_id = checkpoint.get('id')
        if not checkpoint_id:
            raise ValueError('Checkpoint must have an "id" field')

        doc_id = checkpoint_id

        
        checkpoint_data, checkpoint_encoded = self._serialize_field(checkpoint)
        metadata_data, metadata_encoded = self._serialize_field(metadata)

        doc = {
            'id': doc_id,
            THREAD_ID: thread_id,
            CHECKPOINT: checkpoint_data,
            METADATA: metadata_data,
            CHECKPOINT_ENCODED: checkpoint_encoded,
            METADATA_ENCODED: metadata_encoded,
        }

        self.upsert_item(doc)

        return {
            CONFIGURABLE: {
                THREAD_ID: thread_id
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        '''
        Store intermediate writes linked to a checkpoint.

        Args:
            config (RunnableConfig): The runnable configuration.
            writes (Sequence[Tuple[str, Any]]): A sequence of channel and value tuples.
            task_id (str): The task identifier.

        Raises:
            ValueError: If required fields are missing in the config.
        '''
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        if not thread_id:
            raise ValueError(f'"{THREAD_ID}" is required in config["{CONFIGURABLE}"]')

        
        docs = []
        for idx, (channel, value) in enumerate(writes):
            doc_id = f'{thread_id}_{task_id}_{idx}'

            
            value_data, value_encoded = self._serialize_field(value)

            doc = {
                'id': doc_id,
                THREAD_ID: thread_id,
                'task_id': task_id,
                'idx': idx,
                'channel': channel,
                'type': type(value).__name__,
                'value': value_data,
                'value_encoded': value_encoded,
            }
            docs.append(doc)

        self.upsert_items(docs)

class AsyncCosmosDBSaver(BaseCosmosDBSaver, AbstractAsyncContextManager):
    '''
    An asynchronous checkpoint saver that stores checkpoints in an Azure Cosmos DB database.
    '''

    def __init__(
        self,
        *,
        endpoint: str,
        key: str,
        database_name: str,
        container_name: str,
        serde: Optional[SerializerProtocol] = None,
    ) -> None:
        super().__init__(
            database_name=database_name,
            container_name=container_name,
            serde=serde
        )
        self.client = AsyncCosmosClient(endpoint, credential=key)
        self.lock = asyncio.Lock()
        self._initialized = False
        
    async def __aenter__(self) -> Self:
        await self.setup()
        return self
    
    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        await self.close()
        
        
    async def setup(self):
        '''
        Initializes the database and container if not already done.
        Call this if not using 'async with'.
        '''
        if not self._initialized:
            try:
                self.database = await self.client.create_database_if_not_exists(self.database_name)
            except exceptions.CosmosHttpResponseError as e:
                telemetry_client.log_exception('AsyncCosmosDBSaver: Failed to create database')
                raise
            try:
                self.container = await self.database.create_container_if_not_exists(
                    id=self.container_name,
                    partition_key=PartitionKey(path=f'/{THREAD_ID}'),
                    indexing_policy=self.setup_indexing_policy()
                )
            except exceptions.CosmosHttpResponseError as e:
                telemetry_client.log_exception('AsyncCosmosDBSaver: Failed to create container')
                raise

            self._initialized = True
            self.setup_additional()

    def setup_additional(self):
        pass

    async def close(self):
        '''
        Cleans up resources if not using 'async with'.
        '''
        await self.client.close()

    async def upsert_item(self, doc: Dict[str, Any]) -> None:
        '''Upsert an item into the database asynchronously with retry logic.'''
        if not self._initialized:
            raise RuntimeError('AsyncCosmosDBSaver not initialized. Call setup() first.')

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self.lock:
                    await self.container.upsert_item(doc)
                break
            except exceptions.CosmosHttpResponseError as e:
                telemetry_client.log_exception('AsyncCosmosDBSaver: Failed to upsert item')
                if attempt < max_retries - 1 and e.status_code in (429, 503):
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    raise

    async def upsert_items(self, docs: List[Dict[str, Any]]) -> None:
            '''Asynchronously upsert multiple items individually.'''
            if not self._initialized:
                raise RuntimeError('AsyncCosmosDBSaver not initialized. Call setup() first.')

            max_retries = 3
            for doc in docs:
                for attempt in range(max_retries):
                    try:
                        async with self.lock:
                            await self.container.upsert_item(doc)
                        break
                    except exceptions.CosmosHttpResponseError as e:
                        telemetry_client.log_exception('AsyncCosmosDBSaver: Failed to upsert item in batch')
                        if attempt < max_retries - 1 and e.status_code in (429, 503):
                            wait_time = 2 ** attempt
                            await asyncio.sleep(wait_time)
                        else:
                            raise

    def query_items(
        self,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        '''Query items from the database asynchronously with retry logic.'''
        if not self._initialized:
            raise RuntimeError('AsyncCosmosDBSaver not initialized. Call setup() first.')

        async def fetch_items():
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with self.lock:
                        items = self.container.query_items(
                            query=query,
                            parameters=parameters,
                        )
                    async for item in items:
                        yield item
                    break
                except exceptions.CosmosHttpResponseError as e:
                    telemetry_client.log_exception('AsyncCosmosDBSaver: Failed to query items')
                    if attempt < max_retries - 1 and e.status_code in (429, 503):
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
                    else:
                        raise
        return fetch_items()

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        '''Asynchronously retrieve a checkpoint tuple from the database.'''
        if not self._initialized:
            raise RuntimeError('AsyncCosmosDBSaver not initialized. Call setup() first.')
        
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        if not thread_id:
            raise ValueError(f'"{THREAD_ID}" is required in config["{CONFIGURABLE}"]')
        checkpoint_id = get_checkpoint_id(config)
        parameters = [{'name': '@thread_id', 'value': thread_id}]
        if checkpoint_id:
            query = (
                'SELECT * FROM c WHERE c.thread_id = @thread_id AND IS_DEFINED(c.checkpoint) '
                'AND c.checkpoint_id = @checkpoint_id'
            )
            parameters.append({'name': '@checkpoint_id', 'value': checkpoint_id})
        else:
            query = (
                'SELECT * FROM c WHERE c.thread_id = @thread_id AND IS_DEFINED(c.checkpoint) '
                'ORDER BY c.checkpoint_id DESC OFFSET 0 LIMIT 20'
            )

        items_iterable = self.query_items(query=query, parameters=parameters)

        results = []
        async for item in items_iterable:
            results.append(item)

        if results:
            doc = results[0]
            checkpoint = self._deserialize_field(doc, CHECKPOINT, CHECKPOINT_ENCODED)
            metadata = self._deserialize_field(doc, METADATA, METADATA_ENCODED)
            parent_config = (
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                    }
                }
            )
            return CheckpointTuple(
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                    }
                },
                checkpoint,
                metadata,
                parent_config,
            )
        else:
            return None

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        '''Asynchronously list checkpoints from the database.'''
        if not self._initialized:
            raise RuntimeError('AsyncCosmosDBSaver not initialized. Call setup() first.')
        
        parameters = []
        conditions = []
        if config is not None:
            thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
            if not thread_id:
                raise ValueError(f'"{THREAD_ID}" is required in config["{CONFIGURABLE}"]')
            conditions.append('c.thread_id = @thread_id')
            parameters.append({'name': '@thread_id', 'value': thread_id})

        if filter:
            for key, value in filter.items():
                conditions.append(f'c.metadata.{key} = @{key}')
                parameters.append({'name': f'@{key}', 'value': value})

        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        limit_clause = f'OFFSET 0 LIMIT {limit}' if limit else ''

        query = f'SELECT * FROM c WHERE {where_clause} {limit_clause}'

        items_iterable = self.query_items(query=query, parameters=parameters)

        async for doc in items_iterable:
            checkpoint = self._deserialize_field(doc, CHECKPOINT, CHECKPOINT_ENCODED)
            metadata = self._deserialize_field(doc, METADATA, METADATA_ENCODED)
            parent_config = (
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                    }
                }
            )
            yield CheckpointTuple(
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                    }
                },
                checkpoint,
                metadata,
                parent_config,
            )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        '''Asynchronously save a checkpoint to the database.'''
        if not self._initialized:
            raise RuntimeError('AsyncCosmosDBSaver not initialized. Call setup() first.')
        
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        if not thread_id:
            raise ValueError(f'"{THREAD_ID}" is required in config["{CONFIGURABLE}"]')
        
        doc_id = thread_id

        # Serialize checkpoint and metadata
        checkpoint_data, checkpoint_encoded = self._serialize_field(checkpoint)
        metadata_data, metadata_encoded = self._serialize_field(metadata)

        doc = {
            'id': doc_id,
            THREAD_ID: thread_id,
            CHECKPOINT: checkpoint_data,
            METADATA: metadata_data,
            CHECKPOINT_ENCODED: checkpoint_encoded,
            METADATA_ENCODED: metadata_encoded,
        }

        await self.upsert_item(doc)

        return {
            CONFIGURABLE: {
                THREAD_ID: thread_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        '''Asynchronously store intermediate writes linked to a checkpoint.'''
        pass