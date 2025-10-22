from services.llm_services import llm_service_singleton_instance
from utils.prompts import REJECTION_RESPONSE_AGENT_PROMPT
from services.telemetry_client import telemetry_client
from langchain_core.messages import HumanMessage, SystemMessage
import json


class RejectionResponseAgent:
    def __init__(self):
        self.llm = llm_service_singleton_instance.get_llm()
        self.telemetry_client = telemetry_client

    async def get_response(self, user_query: str, messages: list = None) -> dict:
        """
        Generate a rejection response for inappropriate or discriminatory requests.
        
        Args:
            user_query (str): The user's inappropriate query
            messages (list, optional): Conversation history for context
            
        Returns:
            dict: Response containing rejection message and alternatives
        """
        try:
            self.telemetry_client.log_info('Generating rejection response for inappropriate request')
            
            # Generate personalized rejection response using proper message structure
            agent_messages = [
                SystemMessage(content=REJECTION_RESPONSE_AGENT_PROMPT),
                HumanMessage(content=user_query)
            ]
            
            ai_response = await self.llm.ainvoke(agent_messages)
            content = ai_response.content.strip()

            response = {
                'response': content,
                'type': 'rejection',
                'primary_agent': 'Rejection Response'
            }

            self.telemetry_client.log_info('Rejection response generated successfully')
            return response

        except Exception as e:
            self.telemetry_client.log_exception(e, {'error': 'Failed to generate rejection response'})
            
            # Fallback rejection message
            fallback_response = {
                'response': 'I can\'t help with that. Let\'s keep this respectful for everyone.',
                'type': 'rejection',
                'primary_agent': 'Rejection Response'
            }
            
            return fallback_response


# Create singleton instance
rejection_response_agent_singleton_instance = RejectionResponseAgent()
