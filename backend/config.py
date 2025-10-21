import os
from dotenv import load_dotenv

load_dotenv()

# SQL Server Configuration
SQL_SERVER_USERNAME = os.getenv('SQL_SERVER_USERNAME')
SQL_SERVER_NAME = os.getenv('SQL_SERVER_NAME')
SQL_SERVER_PASSWORD = os.getenv('SQL_SERVER_PASSWORD')
SQL_SERVER_DATABASE = os.getenv('SQL_SERVER_DATABASE')

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
AZURE_OPENAI_MAX_TOKENS = os.getenv('AZURE_OPENAI_MAX_TOKENS')

# Application Insights Configuration
APP_INSIGHTS_CONNECTION_STRING = os.getenv('APP_INSIGHTS_CONNECTION_STRING')

# Azure AI Search



required_vars = [
    'SQL_SERVER_USERNAME', 'SQL_SERVER_NAME', 'SQL_SERVER_PASSWORD', 'SQL_SERVER_DATABASE',
    'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_DEPLOYMENT_NAME'
]

for var in required_vars:
    if not globals()[var]:
        raise ValueError(f'Missing required environment variable: {var}')