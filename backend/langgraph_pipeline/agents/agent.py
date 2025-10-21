from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from sqlalchemy import inspect

from Utils.Prompts import SQL_AGENT_SYSTEM_PROMPT
from services.llm_service import llm_service
from data_access.database import database
from services.telemetry_client import telemetry_client


class SQLQuery(BaseModel):
    """Schema for SQL query generation"""
    sql_query: str = Field(description="The SQL query to execute")


class SQLAgent:
    """
    Simple SQL Agent that generates SQL from natural language and executes it.
    Designed to work as a node in a multi-agent orchestration system.
    """
    
    def __init__(self):
        """Initialize SQL Agent with LLM and database"""
        self.telemetry_client = telemetry_client
        self.llm = None
        self.db = None
        self.schema = None
        self._initialize()
    
    def _initialize(self):
        """Set up LLM, database, and cache schema"""
        try:
            self.llm = llm_service.get_llm()
            self.db = database.get_db()
            self.schema = self._get_database_schema()
            self.telemetry_client.log_info('SQL Agent initialized successfully')
        except Exception as e:
            self.telemetry_client.log_exception(e, {"error": "Failed to initialize SQL Agent"})
            raise
    
    def _get_database_schema(self) -> str:
        """Retrieve complete database schema information"""
        try:
            inspector = inspect(self.db._engine)
            schema = ""
            
            for table_name in inspector.get_table_names():
                schema += f"Table: {table_name}\n"
                
                for column in inspector.get_columns(table_name):
                    col_info = f"- {column['name']}: {column['type']}"
                    
                    if column.get('primary_key'):
                        col_info += ", Primary Key"
                    
                    # Handle foreign keys
                    fks = column.get('foreign_keys')
                    if fks:
                        for fk in fks:
                            target = f"{fk.column.table.name}.{fk.column.name}"
                            col_info += f", Foreign Key -> {target}"
                    
                    schema += col_info + "\n"
                
                schema += "\n"
            
            self.telemetry_client.log_info("Database schema retrieved successfully")
            return schema
        except Exception as e:
            self.telemetry_client.log_exception(e, {"error": "Failed to get schema"})
            return "Schema unavailable"
    
    def _generate_sql(self, user_query: str, user_id: str = None) -> str:
        """
        Generate SQL query from natural language question.
        
        Args:
            user_query: Natural language question
            user_id: Optional user ID for scoped queries
            
        Returns:
            SQL query string
        """
        try:
            self.telemetry_client.log_info(f"Generating SQL for: {user_query[:50]}...")
            
            # Build system prompt with schema
            system_prompt = f"""{SQL_AGENT_SYSTEM_PROMPT}

Database Schema:
{self.schema}

Instructions:
- Generate accurate SQL queries based on the schema above
- Use proper JOINs when querying related tables
- Use meaningful aliases (e.g., food.name AS food_name)
- If user_id is provided, scope queries to that user when relevant
- Return ONLY the SQL query, no explanations or formatting
"""
            
            # Add user context if provided
            user_context = f"\nCurrent user_id: {user_id}" if user_id else ""
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt + user_context),
                ("human", "Generate SQL for: {question}")
            ])
            
            # Generate SQL using structured output
            structured_llm = self.llm.with_structured_output(SQLQuery)
            chain = prompt | structured_llm
            result = chain.invoke({"question": user_query})
            
            sql_query = result.sql_query.strip()
            self.telemetry_client.log_info(f"Generated SQL: {sql_query}")
            
            return sql_query
            
        except Exception as e:
            self.telemetry_client.log_exception(e, {"error": "SQL generation failed"})
            raise Exception(f"Failed to generate SQL: {str(e)}")
    
    def _execute_sql(self, sql_query: str) -> str:
        """
        Execute SQL query against database.
        
        Args:
            sql_query: SQL query to execute
            
        Returns:
            Query results as string
        """
        try:
            self.telemetry_client.log_info(f"Executing SQL: {sql_query[:100]}...")
            
            result = self.db.run(sql_query)
            
            if result:
                self.telemetry_client.log_info("SQL executed successfully")
                return result
            else:
                return "No results found."
                
        except Exception as e:
            error_msg = f"Database error: {str(e)}"
            self.telemetry_client.log_exception(e, {"error": "SQL execution failed"})
            raise Exception(error_msg)
    
    def _format_response(self, user_query: str, sql_query: str, results: str) -> str:
        """
        Convert SQL results into natural language response.
        
        Args:
            user_query: Original user question
            sql_query: Executed SQL query
            results: Query results
            
        Returns:
            Natural language response
        """
        try:
            self.telemetry_client.log_info("Formatting response in natural language")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful assistant that converts SQL query results into clear, natural language responses.

Guidelines:
- Provide a direct, friendly answer to the user's question
- Use the data from the results naturally
- Keep it conversational and concise
- Don't mention technical details like SQL or databases
- If no results, explain that clearly"""),
                ("human", """User asked: {question}

SQL executed: {sql_query}

Results: {results}

Provide a natural language answer:""")
            ])
            
            chain = prompt | self.llm | StrOutputParser()
            response = chain.invoke({
                "question": user_query,
                "sql_query": sql_query,
                "results": results
            })
            
            self.telemetry_client.log_info("Response formatted successfully")
            return response
            
        except Exception as e:
            self.telemetry_client.log_exception(e, {"error": "Response formatting failed"})
            # Fallback: return raw results
            return f"Here's what I found:\n{results}"
    
    async def get_response(self, user_query: str, user_id: str = None) -> Dict[str, Any]:
        """
        Process user query: Generate SQL → Execute → Format response.
        
        Args:
            user_query: Natural language question from user
            user_id: Optional user ID for context
            
        Returns:
            Dictionary with 'response' key containing natural language answer
        """
        self.telemetry_client.log_info(
            f"Processing query from user {user_id or 'unknown'}: {user_query[:50]}..."
        )
        
        try:
            # Step 1: Generate SQL query
            sql_query = self._generate_sql(user_query, user_id)
            
            if not sql_query:
                return {"response": "I couldn't generate a query for that question."}
            
            # Step 2: Execute SQL
            try:
                results = self._execute_sql(sql_query)
            except Exception as db_error:
                return {"response": f"I encountered an error: {str(db_error)}"}
            
            # Step 3: Format natural language response
            natural_response = self._format_response(user_query, sql_query, results)
            
            return {"response": natural_response}
            
        except Exception as e:
            self.telemetry_client.log_exception(e, {"error": "Failed to process query"})
            return {"response": "I'm having trouble processing your request. Please try rephrasing your question."}
    
    def get_schema(self) -> str:
        """Get the cached database schema"""
        return self.schema


# Singleton instance
sql_agent = SQLAgent()