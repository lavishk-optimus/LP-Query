import json
import logging
from typing import List, Dict, Any, Optional
from .prompts import FUND_EXTRACTION_SYSTEM_PROMPT, FUND_EXTRACTION_USER_PROMPT
from config import AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME, AZURE_OPENAI_API_VERSION  
try:
    from openai import AzureOpenAI
except ImportError:
    AzureOpenAI = None

from config import config


logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-based fund data extraction using Azure AI Foundry"""
    
    def __init__(self):
        """Initialize the LLM service with Azure OpenAI client"""
        self.client = None
        self.deployment_name = None
        
        if self._init_azure_openai():
            logger.info("LLMService initialized with Azure AI Foundry deployment")
        else:
            raise ValueError(
                "Failed to initialize Azure OpenAI. Please check your Azure AI Foundry configuration."
            )
    
    def _init_azure_openai(self) -> bool:
        """Initialize Azure OpenAI client for Azure AI Foundry"""
        try:
            if AzureOpenAI is None:
                logger.error("openai package not installed. Install with: pip install openai>=1.35.0")
                return False

            azure_endpoint = AZURE_OPENAI_ENDPOINT
            azure_key = AZURE_OPENAI_API_KEY
            deployment_name = AZURE_OPENAI_DEPLOYMENT_NAME
            api_version = AZURE_OPENAI_API_VERSION

            if not azure_endpoint:
                logger.error("AZURE_OPENAI_ENDPOINT not configured")
                return False
            if not azure_key:
                logger.error("AZURE_OPENAI_KEY not configured")
                return False
            if not deployment_name:
                logger.error("AZURE_OPENAI_DEPLOYMENT_NAME not configured")
                return False
            
            self.client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_key,
                api_version=api_version
            )
            self.deployment_name = deployment_name
            
            logger.info(f"Azure OpenAI client initialized with deployment: {deployment_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI: {str(e)}")
            return False
    
    def get_funds_data(self, text_content: str) -> List[Dict[str, Any]]:
        """
        Extract structured fund data from text using LLM
        
        Args:
            text_content (str): Raw text content from document
            
        Returns:
            List[Dict[str, Any]]: List of extracted fund data dictionaries
            
        Raises:
            ValueError: If no LLM client is configured
            Exception: For LLM API errors or parsing errors
        """
        if not self.client:
            raise ValueError(
                "Azure OpenAI client not initialized. Please check your Azure AI Foundry configuration."
            )
        
        if not text_content or not text_content.strip():
            logger.warning("Empty text content provided")
            return []
        
        try:
            logger.info(f"Extracting fund data from text ({len(text_content)} characters)")
            
            # Prepare the prompt
            user_prompt = FUND_EXTRACTION_USER_PROMPT.format(text_content=text_content)
            
            # Call Azure OpenAI with deployment name
            response = self.client.chat.completions.create(
                model=self.deployment_name,  # Use deployment name instead of model name
                messages=[
                    {"role": "system", "content": FUND_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Low temperature for consistent extraction
            )
            
            # Extract and parse response
            response_content = response.choices[0].message.content.strip()
            logger.info(f"LLM response received ({len(response_content)} characters)")
            
            # Parse JSON response
            try:
                funds_data = json.loads(response_content)
                logger.info(f"Raw LLM response type: {type(funds_data)}")
                
                # Handle case where response is wrapped in an object
                if isinstance(funds_data, dict) and 'funds' in funds_data:
                    funds_data = funds_data['funds']
                    logger.info("Extracted funds from 'funds' key")
                elif isinstance(funds_data, dict) and len(funds_data) == 1:
                    # If it's a single key-value pair, try to get the array value
                    for key, value in funds_data.items():
                        if isinstance(value, list):
                            funds_data = value
                            logger.info(f"Extracted funds from '{key}' key")
                            break
                
                # Ensure we have a list
                if not isinstance(funds_data, list):
                    logger.warning("LLM response is not a list, wrapping in list")
                    funds_data = [funds_data] if funds_data else []
                
                logger.info(f"Found {len(funds_data)} fund records before cleaning")
                
                # Log first fund structure for debugging
                if funds_data:
                    logger.info(f"First fund structure: {list(funds_data[0].keys()) if isinstance(funds_data[0], dict) else 'Not a dict'}")
                
                # Check if we got only one fund when the text seems to contain multiple
                if len(funds_data) == 1 and len(text_content) > 5000:
                    logger.warning("LLM returned only 1 fund but input text is large - may have missed multiple funds")
                    logger.warning("Consider reviewing the LLM response for completeness")
                
                # Validate and clean the data
                cleaned_funds = self._validate_and_clean_funds(funds_data)
                
                logger.info(f"Successfully extracted {len(cleaned_funds)} funds")
                return cleaned_funds
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
                logger.error(f"Response content: {response_content[:500]}...")
                
                # Try to extract JSON from response if it's wrapped in text
                try:
                    # Look for JSON array in the response
                    start_idx = response_content.find('[')
                    end_idx = response_content.rfind(']') + 1
                    
                    if start_idx != -1 and end_idx > start_idx:
                        json_str = response_content[start_idx:end_idx]
                        funds_data = json.loads(json_str)
                        cleaned_funds = self._validate_and_clean_funds(funds_data)
                        logger.info(f"Recovered and extracted {len(cleaned_funds)} funds from malformed response")
                        return cleaned_funds
                    
                except Exception:
                    pass
                
                raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error extracting funds data: {str(e)}")
            raise
    
    def _supports_json_mode(self) -> bool:
        """Check if the current deployment supports JSON mode"""
        # Most Azure AI Foundry deployments support JSON mode
        # You can customize this based on your specific deployment
        return True
    
    def _validate_and_clean_funds(self, funds_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate and clean extracted fund data
        
        Args:
            funds_data: Raw fund data from LLM
            
        Returns:
            List[Dict[str, Any]]: Cleaned and validated fund data
        """
        cleaned_funds = []
        
        # Field mapping from document format to model format
        field_mapping = {
            'fund_name': ['fund_name', 'Fund Name', 'name'],
            'vintage': ['vintage', 'Vintage', 'year'],
            'commitment': ['commitment', 'Commitment', 'committed_capital'],
            'paid_in': ['paid_in', 'Paid-In', 'Paid In', 'paid_in_capital'],
            'nav': ['nav', 'NAV', 'net_asset_value'],
            'net_irr': ['net_irr', 'Net IRR', 'irr', 'IRR'],
            'dpi': ['dpi', 'DPI', 'distributions_paid_in'],
            'tvpi': ['tvpi', 'TVPI', 'total_value_paid_in'],
            'pme_vs_index': ['pme_vs_index', 'PME vs Index', 'pme', 'PME'],
            'unfunded': ['unfunded', 'Unfunded', 'remaining_commitment'],
            'status': ['status', 'Status', 'lifecycle_stage'],
            'last_reported': ['last_reported', 'Last Reported', 'report_date']
        }
        
        logger.info(f"Processing {len(funds_data)} fund records from LLM")
        
        for i, fund in enumerate(funds_data):
            if not isinstance(fund, dict):
                logger.warning(f"Fund {i} is not a dictionary, skipping")
                continue
            
            logger.info(f"Processing fund {i+1}: {fund.keys()}")
            cleaned_fund = {}
            
            # Map and validate each field
            for target_field, possible_sources in field_mapping.items():
                value = None
                
                # Try to find the field value using different possible names
                for source_field in possible_sources:
                    if source_field in fund:
                        value = fund[source_field]
                        break
                
                # Clean and validate the field value
                if target_field == 'fund_name':
                    cleaned_fund[target_field] = str(value) if value else f"Unknown Fund {i+1}"
                elif target_field == 'vintage':
                    try:
                        cleaned_fund[target_field] = int(value) if value else 2000
                    except (ValueError, TypeError):
                        cleaned_fund[target_field] = 2000
                elif target_field in ['commitment', 'paid_in', 'nav', 'unfunded']:
                    # Handle monetary values that might have $ and commas
                    try:
                        if isinstance(value, str):
                            # Remove $ and commas, handle "M" for millions
                            clean_value = value.replace('$', '').replace(',', '')
                            if 'M' in clean_value or 'million' in clean_value.lower():
                                # Convert millions to actual number
                                numeric_part = clean_value.replace('M', '').replace('million', '').strip()
                                cleaned_fund[target_field] = int(float(numeric_part) * 1000000)
                            else:
                                cleaned_fund[target_field] = int(float(clean_value))
                        else:
                            cleaned_fund[target_field] = int(value) if value is not None else 0
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse {target_field} value: {value}")
                        cleaned_fund[target_field] = 0
                elif target_field in ['net_irr', 'dpi', 'tvpi', 'pme_vs_index']:
                    # Handle percentage and ratio values
                    try:
                        if isinstance(value, str):
                            # Remove % sign for IRR and PME
                            clean_value = value.replace('%', '').replace('+', '').replace('−', '-').replace('x', '').strip()
                            cleaned_fund[target_field] = float(clean_value)
                        else:
                            cleaned_fund[target_field] = float(value) if value is not None else 0.0
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse {target_field} value: {value}")
                        cleaned_fund[target_field] = 0.0
                elif target_field == 'status':
                    cleaned_fund[target_field] = str(value) if value else "Unknown"
                elif target_field == 'last_reported':
                    # Handle date format
                    if value:
                        date_str = str(value)
                        # Basic date validation (YYYY-MM-DD)
                        if len(date_str) == 10 and date_str.count('-') == 2:
                            cleaned_fund[target_field] = date_str
                        else:
                            # Try to parse other date formats or use default
                            cleaned_fund[target_field] = "2025-06-30"
                    else:
                        cleaned_fund[target_field] = "2025-06-30"
            
            # Calculate unfunded if not provided or incorrect
            if cleaned_fund['commitment'] and cleaned_fund['paid_in']:
                calculated_unfunded = cleaned_fund['commitment'] - cleaned_fund['paid_in']
                if abs(cleaned_fund['unfunded'] - calculated_unfunded) > 1000:  # Allow small rounding differences
                    logger.info(f"Recalculating unfunded for {cleaned_fund['fund_name']}: {calculated_unfunded}")
                    cleaned_fund['unfunded'] = calculated_unfunded
            
            logger.info(f"Successfully processed fund: {cleaned_fund['fund_name']}")
            cleaned_funds.append(cleaned_fund)
        
        logger.info(f"Successfully cleaned {len(cleaned_funds)} funds")
        return cleaned_funds