from typing import Dict, Any
from .services.llm_service import llm_service
from .agents.sql_agent import sql_agent_singleton_instance
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

async def _classify_query(query: str) -> bool:
    """
    Use LLM to determine if a query requires database access.
    Returns True if the query needs database access, False otherwise.
    """
    llm = llm_service.get_llm()
    system_prompt = """You are a query classifier. Your task is to determine if a user query requires database access or not.
Respond with only 'true' for queries that need database access (like querying records, getting statistics, or retrieving data) 
or 'false' for general knowledge or non-data queries. 

Examples of database queries:
- Show me all sales from last month
- How many employees are in the IT department?
- What's the average salary in marketing?
- List all products under $100
- Get customer details for ID 123

Examples of non-database queries:
- What is machine learning?
- How does photosynthesis work?
- Write a Python function to sort a list
- Explain quantum computing
- What's the weather like today?"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Query: {query}\nDoes this query require database access? Answer with only 'true' or 'false':")
    ]
    
    try:
        response = await llm.ainvoke(messages)
        return response.content.strip().lower() == 'true'
    except Exception:
        return False

async def process_query(state):
    """
    Main node that processes queries and routes them to appropriate handlers.
    Uses the SQL agent for data queries and general LLM for other queries.
    """
    messages = state['messages']
    if not messages:
        return {"messages": [AIMessage(content="No query provided.")]}
    
    # Get the user's query from the last message
    last_message = messages[-1]
    query = last_message.content if isinstance(last_message, HumanMessage) else str(last_message)
    
    # Use LLM to classify the query
    is_data_query = await _classify_query(query)
    
    if is_data_query:
        try:
            # Use SQL agent for data queries
            result = await sql_agent_singleton_instance.get_response(query)
            response = result.get('response', 'Unable to process database query.')
        except Exception as e:
            response = f"Error processing database query: {str(e)}"
    else:
        try:
            # Use general LLM for other queries
            llm = llm_service.get_llm()
            response = await llm.ainvoke(messages)
            response = response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            response = f"Error processing query: {str(e)}"
    
    return {"messages": [AIMessage(content=response)]}