import os
from langchain_openai import AzureChatOpenAI
from typing import List, Optional
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file


def create_azure_llm(tools: Optional[List] = None):
    """Create Azure OpenAI LLM with environment-based configuration."""
    
    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        temperature=0.1,
        max_tokens=1000,
        streaming=True
    )
    
    if tools:
        return llm.bind_tools(tools)
    
    return llm