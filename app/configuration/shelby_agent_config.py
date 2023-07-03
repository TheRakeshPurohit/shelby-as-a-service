from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class AppConfig(BaseModel):
    tiktoken_encoding_model: Optional[str] = 'text-embedding-ada-002'
    openai_timeout_seconds: float = 180.0
    embedding_model: Optional[str] = 'text-embedding-ada-002'
    vectorstore_environment: Optional[str] = 'us-central1-gcp'
    vectorstore_index: Optional[str] = os.getenv('PINECONE_INDEX')
    vectorstore_namespace: Optional[str] = 'tatum'
    vectorstore_top_k: int = 3
    llm_model: str = 'gpt-4'
    max_docs_tokens: int = 5000
    max_docs_used = int(os.getenv('MAX_DOCS_USED', '3'))
    prompt_template_name: Optional[str] = 'prompt_template.yaml'
    max_response_tokens = int(os.getenv('MAX_RESPONSE_TOKENS', '600'))

