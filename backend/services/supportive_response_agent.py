from services.llm_service import llm_service
from utils.prompts import SUPPORTIVE_RESPONSE_AGENT_PROMPT
from services.telemetry_client import telemetry_client
from langchain_core.messages import HumanMessage, SystemMessage
import json


class SupportiveResponseAgent:
    def __init__(self):
        self.llm = llm_service.get_llm()
        self.telemetry_client = telemetry_client

    async def get_response(self, user_query: str, messages: list = None) -> dict:
        """
        Generate a supportive response for users experiencing emotional distress.
        
        Args:
            user_query (str): The user's query showing emotional distress
            messages (list, optional): Conversation history for context
            
        Returns:
            dict: Response containing supportive message
        """
        try:
            self.telemetry_client.log_info('Generating supportive response for emotional distress')
            
            # Generate personalized supportive response using proper message structure
            agent_messages = [
                SystemMessage(content=SUPPORTIVE_RESPONSE_AGENT_PROMPT),
                HumanMessage(content=user_query)
            ]
            
            ai_response = await self.llm.ainvoke(agent_messages)
            content = ai_response.content.strip()

            response = {
                'response': content,
                'type': 'supportive',
                'primary_agent': 'Supportive Response'
            }

            self.telemetry_client.log_info('Supportive response generated successfully')
            return response

        except Exception as e:
            self.telemetry_client.log_exception(e, {'error': 'Failed to generate supportive response'})
            
            # Fallback supportive message
            fallback_response = {
                'response': 'I\'m really sorry you\'re feeling this way. You\'re not alone. Please consider reaching out to a mental health professional or a crisis line like https://findahelpline.com.',
                'type': 'supportive',
                'primary_agent': 'Supportive Response'
            }
            
            return fallback_response


# Create singleton instance
supportive_response_agent_singleton_instance = SupportiveResponseAgent()
