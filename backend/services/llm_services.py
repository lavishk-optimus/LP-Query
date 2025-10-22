from services.telemetry_client import telemetry_client
from langchain_openai import AzureChatOpenAI

from config import (
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_MAX_TOKENS,
    AZURE_OPENAI_API_KEY
)

class LLMService:
    def __init__(self):
        '''Initialize Azure OpenAI Chat Model''' 
        self.llm = AzureChatOpenAI(
            deployment_name = AZURE_OPENAI_DEPLOYMENT_NAME,
            api_key = AZURE_OPENAI_API_KEY,
            api_version = AZURE_OPENAI_API_VERSION,
            temperature = 0,
            max_tokens = AZURE_OPENAI_MAX_TOKENS,
            streaming = True
        )
        self.telemetry_client = telemetry_client
        self.telemetry_client.log_info('Initialized successfully Azure OpenAI Chat Model')

    def get_llm(self):
        '''Return the initialized LLM instance'''
        return self.llm

# Singleton instance
llm_service_singleton_instance = LLMService()
