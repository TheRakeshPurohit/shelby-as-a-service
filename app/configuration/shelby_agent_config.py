from pydantic import BaseModel
from typing import Optional
import os
import json
from dotenv import load_dotenv

load_dotenv()


class AppConfig(BaseModel):
    tiktoken_encoding_model: Optional[str] = 'text-embedding-ada-002'
    openai_timeout_seconds: float = 180.0
    # llm_model: str = 'gpt-4'
    # tiktoken_encoding_model: str = 'gpt-4'
    prompt_template_path: Optional[str] = 'app/prompt_templates/'
    # DocsAgent
    embedding_model: Optional[str] = 'text-embedding-ada-002'
    docs_llm_model: str = 'gpt-4'
    vectorstore_environment: Optional[str] = 'us-central1-gcp'
    vectorstore_top_k: int = 3
    vectorstore_index: Optional[str] = os.getenv('PINECONE_INDEX')
    namespaces_str = os.getenv('NAMESPACES', '{}')
    vectorstore_namespaces = json.loads(namespaces_str)
    max_docs_tokens: int = 5000
    max_docs_used = int(os.getenv('MAX_DOCS_USED', '3'))
    max_response_tokens = int(os.getenv('MAX_RESPONSE_TOKENS', '300'))
    # APIAgent
    select_operationID_llm_model: str = 'gpt-4'
    create_function_llm_model: str = 'gpt-4'
    populate_function_llm_model: str = 'gpt-4'
    # select_endpoint_llm_model: str = 'gpt-3.5-turbo-16k-0613'
    action_llm_model: str = 'gpt-4'
    API_spec_path: str = 'data/minified_openAPI_specs/'


