from pydantic import BaseModel
from typing import Dict, Optional
import os
import json

from dotenv import load_dotenv
load_dotenv()

# When this loads it pulls from enviroment variables, or from set variables
# For local use set private information in .env
# For deployment use github secrets

class AppConfig(BaseModel):
    # Must set these
    NAME: str = 'shelby' # lowercase
    TYPE: str = 'discord' # lowercase
    
    # Docs config. Will generate with automation. For now enter manually.
    namespaces_manual_input: Dict[str, str] = {
        "tatum": "blockchain and web3", 
        "deepgram": "ai speech to text services"
        }
    
    # Maybe tweak these
    # ActionAgent
    action_llm_model: str = os.getenv('ACTION_LLM_MODEL', 'gpt-4')
    # QueryAgent
    try:
        ectorstore_namespaces: Dict[str, str] = json.loads(os.getenv('VECTORSTORE_NAMESPACES'))
    except (TypeError, json.JSONDecodeError):
        vectorstore_namespaces: Dict[str, str] = namespaces_manual_input
    query_llm_model: str = os.getenv('QUERY_LLM_MODEL', 'gpt-4')
    vectorstore_top_k: int = int(os.getenv('VECTORSTORE_TOP_K', 3))
    vectorstore_index: str = os.getenv('VECTORSTORE_INDEX', 'shelby-as-a-service')
    vectorstore_environment: str = os.getenv('VECTORSTORE_ENVIRONMENT', 'us-central1-gcp')
    max_docs_tokens: int = int(os.getenv('MAX_DOCS_TOKENS', 5000))
    max_docs_used: int = int(os.getenv('MAX_DOCS_USED', 3))
    max_response_tokens: int = int(os.getenv('MAX_RESPONSE_TOKENS', 300))
    openai_timeout_seconds: float = float(os.getenv('OPENAI_TIMEOUT_SECONDS', 180.0))
    # APIAgent
    select_operationID_llm_model: str = os.getenv('SELECT_OPERATIONID_LLM_MODEL', 'gpt-4')
    create_function_llm_model: str = os.getenv('CREATE_FUNCTION_LLM_MODEL', 'gpt-4')
    populate_function_llm_model: str = os.getenv('POPULATE_FUNCTION_LLM_MODEL', 'gpt-4')
    
    # Set with automation
    GITHUB_ACTION_WORKFLOW_NAME: str = f'{NAME.lower()}_{TYPE.lower()}_build_deploy'
    WORKLOAD_NAME: str = f'{NAME.lower()}-{TYPE.lower()}-sprite'
    WORKLOAD_SLUG: str = f'{NAME.lower()}-{TYPE.lower()}-sprite'
    
    # Don't touch these
    tiktoken_encoding_model: Optional[str] = os.getenv('TIKTOKEN_ENCODING_MODEL', 'text-embedding-ada-002')
    prompt_template_path: Optional[str] = os.getenv('PROMPT_TEMPLATE_PATH', 'app/prompt_templates/')
    API_spec_path: str = os.getenv('API_SPEC_PATH', 'data/minified_openAPI_specs/')
    
