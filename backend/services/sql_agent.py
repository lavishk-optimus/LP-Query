from utils.prompts import SQL_AGENT_SYSTEM_PROMPT, SQL_AGENT_CONTEXT_TEMPLATE
from services.llm_services import llm_service_singleton_instance
from data_access.database import database
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from services.telemetry_client import telemetry_client
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit


class SQLAgent:
    def __init__(self, k: int = 5, callbacks = None, prefix = None):
        '''Initializes SQL Agent with Azure OpenAI and SQL Database using LangGraph's React Agent'''
        self.telemetry_client = telemetry_client

        try:
            self.llm = llm_service_singleton_instance.get_llm()
            self.k = k
            self.callbacks = callbacks

            db = database.get_db()
            self.telemetry_client.log_info('Database connection established')

            toolkit = SQLDatabaseToolkit(db=db, llm=self.llm)
            self.sql_tools = toolkit.get_tools()
            self.telemetry_client.log_info(f'SQL toolkit initialized with {len(self.sql_tools)} tools')

            self.system_prompt = ''
            self._create_agent()

            self.telemetry_client.log_info('SQL Agent initialized successfully')
        except Exception as e:
            self.telemetry_client.log_exception(e, {"error": "Failed to initialize SQL Agent"})
            raise

    def _create_agent(self):
        '''Create the LangGraph React Agent'''
        try:
            self.telemetry_client.log_info('Creating React Agent')
            self.agent_executor = create_react_agent(
                model=self.llm,
                tools=self.sql_tools,
                debug=False
            )
            self.telemetry_client.log_info('React Agent created successfully')
        except Exception as e:
            self.telemetry_client.log_exception(e, {"error": "Failed to create React Agent"})
            raise

    async def get_response(self, user_query: str, user_id: str = "default_user"):
        '''Async method to invoke the agent directly'''
        self.telemetry_client.log_info(f'Processing query: {user_query[:50]}...')

        try:
            self.system_prompt = SQL_AGENT_SYSTEM_PROMPT
            
            formatted_query = SQL_AGENT_CONTEXT_TEMPLATE.format(user_query=user_query)

            human_message = HumanMessage(content = formatted_query)
            agent_messages = [SystemMessage(content = self.system_prompt), human_message]

            self.telemetry_client.log_info('Invoking agent with formatted query')
            result = await self.agent_executor.ainvoke({
                'messages': agent_messages
            })

            final_message = result['messages'][-1]
            self.telemetry_client.log_info('Agent response received successfully')

            if isinstance(final_message, AIMessage):
                return {
                    'response': final_message.content
                }

            return {
                    'response': 'Unable to retrieve response from database.'
                }

        except Exception as e:
            error_message = f'Please Try Again!'
            self.telemetry_client.log_exception(e, {"error": f"Error during agent execution: {e}"})
            return {'response': error_message}

sql_agent_singleton_instance = SQLAgent()