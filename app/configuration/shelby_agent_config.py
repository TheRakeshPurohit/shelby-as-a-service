from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class AppConfig(BaseModel):
    tiktoken_encoding_model: Optional[str] = 'text-embedding-ada-002'
    chunk_size: int = 1000
    chunk_overlap: int = 300
    preprocessor_separators: Optional[str] = None
    openai_timeout_seconds: float = 180.0
    embedding_model: Optional[str] = 'text-embedding-ada-002'
    embedding_max_chunk_size: int = 8191
    embedding_batch_size: int = 8
    vectorstore_environment: Optional[str] = 'us-central1-gcp'
    vectorstore_index: Optional[str] = os.getenv('PINECONE_INDEX')
    vectorstore_dimension: int = 1536
    vectorstore_namespace: Optional[str] = 'tatum'
    vectorstore_upsert_batch_size: int = 50
    vectorstore_top_k: int = 3
    llm_model: str = 'gpt-4'
    max_docs_tokens: int = 5000
    prompt_template_name: Optional[str] = 'prompt_template.yaml'
