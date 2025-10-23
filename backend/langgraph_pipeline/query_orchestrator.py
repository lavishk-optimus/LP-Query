from uuid import uuid4
from services.supportive_response_agent import supportive_response_agent_singleton_instance
from services.rejection_response_agent import rejection_response_agent_singleton_instance
from services.cosmos_checkpointer import AsyncCosmosDBSaver
from config import AZURE_COSMOSDB_ENDPOINT, AZURE_COSMOSDB_NAME, AZURE_COSMOSDB_PRIMARY_KEY
from models.state import Message, State
import copy
from services.sql_agent import sql_agent_singleton_instance
from services.llm_services import llm_service_singleton_instance
from utils.prompts import INITIAL_PROMPT_TEMPLATE
from constants import CONTEXT_LIMIT
from langgraph.graph import StateGraph
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from services.cosmos_client import cosmos_client_singleton_instance, ContainerType
from services.telemetry_client import telemetry_client

import json

class QueryOrchestrator:
    def __init__(self):
        '''Initialize Query Orchestrator with LLM, SQL Agent, and precompile the workflow.'''

        self.llm = llm_service_singleton_instance.get_llm()
        self.sql_agent = sql_agent_singleton_instance
        self.supportive_response_agent = supportive_response_agent_singleton_instance
        self.rejection_response_agent = rejection_response_agent_singleton_instance
        self.cosmos_client = cosmos_client_singleton_instance
        self.workflow = self.create_workflow()
        self.user_query: str | None = None   
        self.telemetry_client = telemetry_client   

    async def brain_node(self, state):
        user_id = state.get('user_id', 'unknown')
        session_id = state.get('session_id', 'unknown')

        try:
            self.user_query = state['messages'][-1].content
            messages = self.limit_context(state)

            self.telemetry_client.log_info('Invoking LLM for initial response', {'user_id': user_id, 'session_id': session_id, 'user_query': self.user_query})
            prompt = INITIAL_PROMPT_TEMPLATE.format(user_query = self.user_query, messages = messages)

            ai_response = await self.llm.ainvoke(prompt)

            if hasattr(ai_response, 'content'):
                content = ai_response.content.strip()
            else:
                content = str(ai_response).strip()

            # Log the LLM response for debugging
            self.telemetry_client.log_info(
                'LLM response received', 
                {
                    'user_id': user_id, 
                    'session_id': session_id, 
                    'llm_response': content[:500] + "..." if len(content) > 500 else content
                }
            )

            tool_message = Message(
                id = str(uuid4()),
                type = 'assistant',
                content = content
            )

            new_state = state.copy()
            new_state['messages'] += [tool_message]

            await self.save_history_to_cosmos(new_state)
            return new_state

        except Exception as e:
            self.telemetry_client.log_exception(e, {'error': 'Failed in brain_node', 'user_id': user_id, 'session_id': session_id})
            error_message = Message(
                id = str(uuid4()),
                type = 'ai',
                content = 'Sorry! I am unable to understand your intent...'
            )

            new_state = state.copy()
            new_state['messages'] += [error_message]

            return new_state
    async def sql_agent_node(self, state):
        '''To SQL Agent for tracking progress'''
        user_id = state.get('user_id', 'unknown')
        session_id = state.get('session_id', 'unknown')

        try:
            self.telemetry_client.log_info('SQL Agent called', {'user_id': user_id, 'session_id': session_id})
            messages = self.limit_context(state)
            response = await self.sql_agent.get_response(user_query = self.user_query, user_id = user_id)
            response['primary_agent'] = "Sql"
            
            tool_message = Message(
                id = str(uuid4()),
                type = 'ai',
                content = str(json.dumps(response))
            )

            new_state = state.copy()
            new_state['messages'] += [tool_message]

            return new_state

        except Exception as e:
            self.telemetry_client.log_exception(e, {'error': 'Failed to fetch the progress results', 'user_id': user_id, 'session_id': session_id})
            error_message = Message(
                id = str(uuid4()),
                type = 'ai',
                content = 'Sorry! Chat limit reached...'
            )

            error_state = state.copy()
            error_state['messages'] += [error_message]

            await self.save_history_to_cosmos(error_state)
            return error_state

    async def default_node(self, state):
        '''Default node for unclear queries'''
        user_id = state.get('user_id', 'unknown')
        session_id = state.get('session_id', 'unknown')

        try:
            self.telemetry_client.log_info('Using default node response', {'user_id': user_id, 'session_id': session_id})
            
            if 'UNCLEAR' in state['messages'][-1].content:
                response = "I am sorry, I am not able to understand your query. Please try again."
            elif 'GREETING:' in state['messages'][-1].content:
                # Extract greeting response after "GREETING: "
                response = state['messages'][-1].content.split('GREETING:', 1)[1].strip()
            elif 'BOT_HELP:' in state['messages'][-1].content:
                # Extract bot help response after "BOT_HELP: "
                response = state['messages'][-1].content.split('BOT_HELP:', 1)[1].strip()
            else:
                response = state['messages'][-1].content

            tool_message = Message(
                id = str(uuid4()),
                type = 'ai',
                content = response
            )

            new_state = state.copy()
            new_state['messages'] += [tool_message]

            await self.save_history_to_cosmos(new_state)
            return new_state

        except Exception as e:
            self.telemetry_client.log_exception(e, {'error': 'Failed in default node', 'user_id': user_id, 'session_id': session_id})
            error_message = Message(
                id = str(uuid4()),
                type = 'ai',
                content = 'Sorry! Something went wrong. Please try again.'
            )

            error_state = state.copy()
            error_state['messages'] += [error_message]
            return error_state

    async def supportive_response_node(self, state):
        '''Invokes the Supportive Response agent for users showing emotional distress'''
        user_id = state.get('user_id', 'unknown')
        session_id = state.get('session_id', 'unknown')

        try:
            if not self.user_query:
                raise ValueError("User query is required")

            self.telemetry_client.log_info('Calling the Supportive Response agent', {'user_id': user_id, 'session_id': session_id})
            messages = self.limit_context(state)

            response = await self.supportive_response_agent.get_response(user_query=str(self.user_query), messages=messages)

            tool_message = Message(
                id=str(uuid4()),
                type='ai',
                content=response['response']
            )

            new_state = state.copy()
            new_state['messages'] += [tool_message]

            await self.save_history_to_cosmos(new_state)
            return new_state

        except Exception as e:
            self.telemetry_client.log_exception(e, {'error': 'Supportive Response Agent execution failed', 'user_id': user_id, 'session_id': session_id})
            
            # Fallback supportive message
            fallback_message = Message(
                id=str(uuid4()),
                type='ai',
                content='I\'m really sorry you\'re feeling this way. You\'re not alone. Please consider reaching out to a mental health professional or a crisis line like https://findahelpline.com.'
            )

            error_state = state.copy()
            error_state['messages'] += [fallback_message]
            return error_state

    async def rejection_response_node(self, state):
        '''Invokes the Rejection Response agent for discriminatory requests'''
        user_id = state.get('user_id', 'unknown')
        session_id = state.get('session_id', 'unknown')

        try:
            if not self.user_query:
                raise ValueError("User query is required")

            self.telemetry_client.log_info('Calling the Rejection Response agent', {'user_id': user_id, 'session_id': session_id})
            messages = self.limit_context(state)

            response = await self.rejection_response_agent.get_response(user_query=str(self.user_query), messages=messages)

            tool_message = Message(
                id=str(uuid4()),
                type='ai',
                content=response['response']
            )

            new_state = state.copy()
            new_state['messages'] += [tool_message]

            await self.save_history_to_cosmos(new_state)
            return new_state

        except Exception as e:
            self.telemetry_client.log_exception(e, {'error': 'Rejection Response Agent execution failed', 'user_id': user_id, 'session_id': session_id})
            
            # Fallback rejection message
            fallback_message = Message(
                id=str(uuid4()),
                type='ai',
                content='I can\'t help with that. Let\'s keep this respectful for everyone.'
            )

            error_state = state.copy()
            error_state['messages'] += [fallback_message]
            return error_state

    def create_workflow(self):
        '''Creates a LangGraph workflow for structured query execution.'''

        graph = StateGraph(State)
        
        graph.add_node('brain_node', self.brain_node)
        # graph.add_node('quiz_generation_agent_node', self.quiz_generation_agent_node)
        # graph.add_node('quiz_evaluation_agent_node', self.quiz_evaluation_agent_node)
        # graph.add_node('deep_dive_agent_node', self.deep_dive_agent_node)
        graph.add_node('sql_agent_node', self.sql_agent_node)
        graph.add_node('default_node', self.default_node)
        graph.add_node('supportive_response_node', self.supportive_response_node)
        graph.add_node('rejection_response_node', self.rejection_response_node)

        graph.set_entry_point('brain_node')

        graph.add_conditional_edges(
            'brain_node',
            self.route_tools,
            {
                'SUPPORTIVE_RESPONSE': 'supportive_response_node',
                'REJECTION_RESPONSE': 'rejection_response_node',
                'SQL_AGENT': 'sql_agent_node', 
                'UNCLEAR': 'default_node',
                'GREETING': 'default_node',
                'BOT_HELP': 'default_node'
            }
        )

        return graph

    async def initialize_orchestrator(self):
        if not all([AZURE_COSMOSDB_ENDPOINT, AZURE_COSMOSDB_PRIMARY_KEY, AZURE_COSMOSDB_NAME]):
            raise ValueError("Missing required Cosmos DB configuration")

        self.cosmos_client = cosmos_client_singleton_instance
        await self.cosmos_client._initialize_cosmos_client()

        self.user_query = None

        checkpointer_async = AsyncCosmosDBSaver(
            endpoint=str(AZURE_COSMOSDB_ENDPOINT),
            key=str(AZURE_COSMOSDB_PRIMARY_KEY),
            database_name=str(AZURE_COSMOSDB_NAME),
            container_name='checkpointer',
            serde=JsonPlusSerializer(),
        )

        await checkpointer_async.setup()
        return self.workflow.compile(checkpointer=checkpointer_async)

    def get_category(self, ai_response):
        # Convert to uppercase for case-insensitive matching
        response_upper = ai_response.upper()
        
        # Primary check: Look for exact category names (preferred format)
        if 'SUPPORTIVE_RESPONSE' in response_upper:
            return 'SUPPORTIVE_RESPONSE'
        
        elif 'REJECTION_RESPONSE' in response_upper:
            return 'REJECTION_RESPONSE'
        
        elif 'SQL_AGENT' in response_upper:
            return 'SQL_AGENT'

        elif 'GREETING' in response_upper:
            return 'GREETING'
        
        elif 'BOT_HELP' in response_upper:
            return 'BOT_HELP'
            
        elif any(phrase in response_upper for phrase in [
            'HELLO', 'HI ', 'GOOD MORNING', 'GOOD AFTERNOON', 'GOOD EVENING',
            'HOW CAN I HELP', 'HOW CAN I ASSIST'
        ]):
            return 'GREETING'
            
        elif any(phrase in response_upper for phrase in [
            'I AM AN', 'I CAN HELP', 'MY CAPABILITIES', 'WHAT I CAN DO'
            
        ]):
            return 'BOT_HELP'
        
        else:
            return 'UNCLEAR'

    def route_tools(self, state):
        content = state['messages'][-1].content
        category = self.get_category(content)
        
        # Add debug logging to track routing decisions
        user_id = state.get('user_id', 'unknown')
        session_id = state.get('session_id', 'unknown')
        
        self.telemetry_client.log_info(
            f'Routing decision: {category}', 
            {
                'user_id': user_id, 
                'session_id': session_id, 
                'ai_response': content[:200] + "..." if len(content) > 200 else content,
                'category': category
            }
        )
        
        return category  

    def limit_context(self, state):
        '''Limit the context to the last CONTEXT_LIMIT messages.'''
        limited_context = state['messages']

        if len(state['messages']) > CONTEXT_LIMIT:
            limited_context = state['messages'][-CONTEXT_LIMIT:]

        return limited_context

    async def save_history_to_cosmos(self, state):
        user_id = state.get('user_id', 'unknown')
        session_id = state.get('session_id', 'unknown')

        try: 
            id = str(state['user_id'] + '$' + state['session_id'])
            item = copy.deepcopy(state)
            item['id'] = id
            message_list = []

            for message in item['messages']:
                if not isinstance(message, dict):
                    message_list += [message.dict()]
                else:
                    message_list += [message]

            item['messages'] = message_list    

            success = await self.cosmos_client.save_item(
                container_type=ContainerType.CONVERSATION,
                item=item,
                partition_key=item['id']
            )
            self.telemetry_client.log_info('Conversation history saved to CosmosDB', {'user_id': user_id, 'session_id': session_id})
            return success

        except Exception as e:
            self.telemetry_client.log_exception(e, {'error': 'Failed to save conversation history', 'user_id': user_id, 'session_id': session_id})
            return False
