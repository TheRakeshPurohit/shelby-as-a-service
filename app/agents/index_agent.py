# region Imports
import os
from typing import List, Union, Iterator
import re, string
import yaml, json
from urllib.parse import urlparse

from dotenv import load_dotenv
from langchain.schema import Document
from langchain.document_loaders import GitbookLoader, SitemapLoader, RecursiveUrlLoader
from langchain.text_splitter import BalancedRecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from pinecone_text.sparse import BM25Encoder
import tiktoken
import pinecone

from agents.logger_agent import LoggerAgent
from configuration.shelby_agent_config import AppConfig
# endregion

class IndexAgent:
    def __init__(self):
        load_dotenv()
        self.log_agent = LoggerAgent('IndexAgent', 'IndexAgent.log', level='INFO')
        self.agent_config = AppConfig() 
        # Loads data sources from file
        with open(self.agent_config.document_sources_filepath, 'r') as stream:
            try:
                self.data_source_config = yaml.safe_load(stream)
            except yaml.YAMLError as e:
                self.log_agent.print_and_log(e)
                
        pinecone.init(
            environment=self.agent_config.vectorstore_environment,
            api_key=self.agent_config.pinecone_api_key, 
        )
        indexes = pinecone.list_indexes()
        if self.agent_config.vectorstore_index not in indexes:
            # create new index
            response = self.create_index()
            self.log_agent.print_and_log(f"Created index: {response}")
            
        self.vectorstore = pinecone.Index(self.agent_config.vectorstore_index)
        stats = self.vectorstore.describe_index_stats()
        self.log_agent.print_and_log(stats)
        
        self.document_sources_resources = []
        # Iterate over each source aka namespace
        for namespace, resources_dict in self.data_source_config.items():
            # Then iterate over each resource within a source
            for resource_name, resource_content in resources_dict['resources'].items():
                try:
                    data_source = DataSourceConfig(self, namespace, resource_name, resource_content)
                    if data_source.enabled == False:
                        continue
                    self.document_sources_resources.append(data_source)
                    self.log_agent.print_and_log(f'Will index: {resource_name}')
                except ValueError as e:
                    self.log_agent.print_and_log(f"Error processing source {resource_name}: {e}")
                    continue
             
    def ingest_docs(self):
        for data_resource in self.document_sources_resources:
            self.log_agent.print_and_log(f'\nNow indexing: {data_resource.resource_name}\n')
            # Load documents
            documents = data_resource.scraper.load()
            
            self.log_agent.print_and_log(f'Docs loaded for indexing: {data_resource.resource_name}')
            
            if not documents:
                raise ValueError("No documents loaded.")
            text_chunks, document_chunks = data_resource.preprocessor.run(documents)
            if not text_chunks:
                raise ValueError("No text_chunks loaded.")
            
            # Saves documents_chunks to folder
            os.makedirs('outputs/document_chunks', exist_ok=True)
            for i, document_chunk in enumerate(document_chunks):
                with open(os.path.join('outputs/document_chunks', f'document_chunk_{i}.md'), 'w') as f:
                    f.write(str(document_chunk))

            # Get dense_embeddings
            dense_embeddings = data_resource.embedding_retriever.embed_documents(text_chunks)

            # Get sparse_embeddings
            # Pretrain "corpus"
            data_resource.bm25_encoder.fit(text_chunks)
            sparse_embeddings = data_resource.bm25_encoder.encode_documents(text_chunks)
            self.log_agent.print_and_log(f'Embedding complete for: {data_resource.resource_name}')
            
            # Get count of vectors in index matching the "resource" metadata field
            index_resource_stats = data_resource.vectorstore.describe_index_stats(filter={'resource_name': data_resource.resource_name})
            self.log_agent.print_and_log(f"stats matching 'resource_name' metadata field: {index_resource_stats}")
            resource_vector_count = index_resource_stats.get('namespaces', {}).get(data_resource.namespace, {}).get('vector_count', 0)

            # If the "resource" already has vectors delete the existing vectors before upserting new vectors
            if resource_vector_count != 0:
                self.clear_resource_name(data_resource)
                
            # Get total count of vectors in index namespace and create new vectors with an id of index_vector_count + 1
            index_stats = data_resource.vectorstore.describe_index_stats()
            index_vector_count = index_stats.get('namespaces', {}).get(data_resource.namespace, {}).get('vector_count', 0)
            if index_vector_count != 0:
                index_vector_count += 1
                
            vectors_to_upsert = []
            for i, document_chunk in enumerate(document_chunks):
                prepared_vector = {
                    "id": "id" + str(index_vector_count),
                    "values": dense_embeddings[i],  
                    "metadata": document_chunk,  
                    'sparse_values': sparse_embeddings[i]
                }
                index_vector_count += 1
                vectors_to_upsert.append(prepared_vector)

            self.log_agent.print_and_log(f"{len(vectors_to_upsert)} chunks as vectors to upsert")
            data_resource.vectorstore.upsert(
                vectors=vectors_to_upsert,               
                namespace=data_resource.namespace,
                batch_size=self.agent_config.vectorstore_upsert_batch_size,
                show_progress=True                 
            )
            self.log_agent.print_and_log(f'Indexing complete for: {data_resource.resource_name}')
        index_stats = data_resource.vectorstore.describe_index_stats()
        self.log_agent.print_and_log(index_stats)
    
    def delete_index(self):
        res = self.document_sources_resources[0].vectorstore.describe_index_stats()
        self.log_agent.print_and_log(res)
        res = pinecone.delete_index(self.agent_config.vectorstore_index)
        self.log_agent.print_and_log(res)
        res = self.document_sources_resources[0].vectorstore.describe_index_stats()
        self.log_agent.print_and_log(res)

    def clear_index(self):
        for data_source in self.document_sources_resources:
            stats = data_source.vectorstore.describe_index_stats()
            self.log_agent.print_and_log(stats)
            for key in stats['namespaces']:
                data_source.vectorstore.delete(deleteAll='true', namespace=key)
            stats = data_source.vectorstore.describe_index_stats()
            self.log_agent.print_and_log(stats)
    
    def clear_namespace(self, namespace):
        stats =  self.document_sources_resources[0].vectorstore.describe_index_stats()
        self.log_agent.print_and_log(stats)
        self.log_agent.print_and_log(f'Clearing namespace: {namespace}')
        self.document_sources_resources[0].vectorstore.delete(deleteAll='true', namespace=namespace)
        stats =  self.document_sources_resources[0].vectorstore.describe_index_stats()
        self.log_agent.print_and_log(stats)
    
    def clear_resource_name(self, data_resource):
        data_resource.vectorstore.delete(
        namespace=data_resource.namespace,
        delete_all=False, 
        filter={'resource_name': data_resource.resource_name}
        )
        self.log_agent.print_and_log(f"Removed pre-existing vectors in index with metadata fields 'resource_name': {data_resource.resource_name}")
        index_resource_stats = data_resource.vectorstore.describe_index_stats(filter={'resource_name': data_resource.resource_name})
        self.log_agent.print_and_log(f"New stats matching 'resource_name' metadata field: {index_resource_stats}")
        
    def create_index(self):
        metadata_config = {
            "indexed": self.agent_config.indexed_metadata
        }
        # Prepare log message
        log_message = (
            f"Creating new index with the following configuration:\n"
            f" - Index Name: {self.agent_config.vectorstore_index}\n"
            f" - Dimension: {self.agent_config.vectorstore_dimension}\n"
            f" - Metric: {self.agent_config.vectorstore_metric}\n"
            f" - Pod Type: {self.agent_config.vectorstore_pod_type}\n"
            f" - Metadata Config: {metadata_config}"
        )
        # Log the message
        self.log_agent.print_and_log(log_message)
        
        response = pinecone.create_index(
            name=self.agent_config.vectorstore_index, 
            dimension=self.agent_config.vectorstore_dimension, 
            metric=self.agent_config.vectorstore_metric,
            pod_type=self.agent_config.vectorstore_pod_type,
            metadata_config=metadata_config
            )
        
        return response
        
class DataSourceConfig:
    def __init__(self, index_agent: IndexAgent, namespace, resource_name, resource_content):
        self.index_agent = index_agent
  
        self.index_name = index_agent.agent_config.vectorstore_index
        self.indexed_metadata = index_agent.agent_config.indexed_metadata
        
        # From document_sources.yaml
        self.namespace: str = namespace
        self.resource_name: str = resource_name
        self.filter_url: str = resource_content.get('filter_url')
        self.enabled: bool = resource_content.get('enabled')
        self.load_all_paths: bool = resource_content.get('load_all_paths')
        self.target_url: str = resource_content.get('target_url')
        self.target_type: str = resource_content.get('target_type')
        self.doc_type: str = resource_content.get('doc_type')

        # Check if any value is None
        attributes = [
            self.namespace,
            self.resource_name, 
            self.index_name, 
            self.enabled,
            self.target_url, 
            self.target_type, 
            self.doc_type
            ]
        if not all(attr is not None and attr != "" for attr in attributes):
            raise ValueError("Some required fields are missing or have no value.")
   
        pinecone.init(
            api_key=index_agent.agent_config.pinecone_api_key, 
            environment=index_agent.agent_config.vectorstore_environment
        )
        
        # Initialize vectorstore index
        self.vectorstore = pinecone.Index(self.index_name)
        
        match self.target_type:
            case 'gitbook':
                self.scraper = GitbookLoader(
                    web_page=self.target_url,
                    load_all_paths=self.load_all_paths
                    )
                self.content_type = "text"
            case 'sitemap':
                self.scraper = SitemapLoader(
                    self.target_url,
                    filter_urls=[self.filter_url]                 
                    )
                self.content_type = "text"
            case 'generic':
                self.scraper = CustomScraper(self)
                self.content_type = "text"
            case 'openapi':
                self.scraper = OpenAPILoader(self)
                self.content_type = "openapi"
            case _:
                raise ValueError(f"Invalid target type: {self.target_type}")
            
        match self.content_type:
            case 'text':
                self.preprocessor = CustomPreProcessor(self)
            case 'openapi':
                self.preprocessor = OpenAPIPreProcessor(self)
            case _:
                raise ValueError("Invalid target type: should be text, html, or code.")
            
        self.embedding_retriever = OpenAIEmbeddings(
            model=index_agent.agent_config.embedding_model,
            embedding_ctx_length=index_agent.agent_config.embedding_max_chunk_size,
            openai_api_key=index_agent.agent_config.openai_api_key,
            chunk_size=index_agent.agent_config.embedding_batch_size,
            request_timeout=index_agent.agent_config.openai_timeout_seconds
        )

        self.bm25_encoder = BM25Encoder()

class CustomPreProcessor:
    def __init__(self, data_source_config: DataSourceConfig):
        self.data_source_config = data_source_config

        self.tiktoken_encoding_model=data_source_config.index_agent.agent_config.tiktoken_encoding_model
        self.tokenizer = tiktoken.encoding_for_model(data_source_config.index_agent.agent_config.tiktoken_encoding_model)
        
        # Defines which chars can be kept; Alpha-numeric chars, punctionation, and whitespaces.
        self.printable = string.printable

        self.text_splitter = BalancedRecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name=self.tiktoken_encoding_model,
            goal_length=data_source_config.index_agent.agent_config.text_splitter_goal_length,
            max_length=data_source_config.index_agent.agent_config.text_splitter_max_length
        )

    def run(self, documents: Union[Document, List[Document]]) -> List[Document]:
        documents_as_chunks = []
        text_as_chunks = []
        for page in documents:
            
            # If no page title use the url and the resource type
            if not page.metadata.get('title'):
                parsed_url = urlparse(page.metadata.get('loc'))
                _, tail = os.path.split(parsed_url.path)
                # Strip anything with "." like ".html"
                root, _ = os.path.splitext(tail)
                page.metadata['title'] = f'{self.data_source_config.resource_name}: {root}'
                
                
            self.data_source_config.index_agent.log_agent.print_and_log(page.metadata['title'])
            # Remove bad chars
            page.page_content = re.sub(f'[^{re.escape(self.printable)}]', '', page.page_content)
            # Reduces any sequential occurences of a specific whitespace (' \t\n\r\v\f') to just two of those specific whitespaces
            # Create a dictionary to map each whitespace character to its escape sequence (if needed)
            whitespace_characters = {
                ' ': r' ',
                '\t': r'\t',
                '\n': r'\n',
                '\r': r'\r',
                '\v': r'\v',
                '\f': r'\f',
            }
            # Replace any sequential occurrences of each whitespace character with just two
            for char, escape_sequence in whitespace_characters.items():
                pattern = escape_sequence + "{3,}"
                replacement = char * 2
                page.page_content = re.sub(pattern, replacement, page.page_content)
            # page.page_content = re.sub('\n{3,}', '\n\n', page.page_content)
            # Skip if too small
            if self._tiktoken_len(page.page_content) < self.data_source_config.index_agent.agent_config.preprocessor_min_length:
                self.data_source_config.index_agent.log_agent.print_and_log(f'page too small: {self._tiktoken_len(page.page_content)}')
                continue
            # Split into chunks
            text_chunks = self.text_splitter.split_text(page.page_content)
            for text_chunk in text_chunks:
                document_chunk, text_chunk = self.append_metadata(text_chunk, page)
                documents_as_chunks.append(document_chunk)
                text_as_chunks.append(text_chunk.lower())
        
        self.data_source_config.index_agent.log_agent.print_and_log(f'Total pages: {len(documents)}')
        self.data_source_config.index_agent.log_agent.print_and_log(f'Total chunks: {len(documents_as_chunks)}')
        if not documents_as_chunks:
            return
        token_counts = [
            self._tiktoken_len(chunk) for chunk in text_as_chunks
        ]
        self.data_source_config.index_agent.log_agent.print_and_log(f'Min: {min(token_counts)}')
        self.data_source_config.index_agent.log_agent.print_and_log(f'Avg: {int(sum(token_counts) / len(token_counts))}')
        self.data_source_config.index_agent.log_agent.print_and_log(f'Max: {max(token_counts)}')
        self.data_source_config.index_agent.log_agent.print_and_log(f'Total tokens: {int(sum(token_counts))}')

        return text_as_chunks, documents_as_chunks
    
    def append_metadata(self, text_chunk, page):
        # Document chunks are the metadata uploaded to vectorstore
        document_chunk = {
                    "content": text_chunk, 
                    "url": page.metadata['source'].strip(), 
                    "title": page.metadata['title'],
                    "resource_name": self.data_source_config.resource_name,
                    "target_type": self.data_source_config.target_type,
                    "doc_type": self.data_source_config.doc_type
                    }
        # Text chunks here are used to create embeddings
        text_chunk =  f"{text_chunk} title: {page.metadata['title']}"

        return document_chunk, text_chunk
    
    def _tiktoken_len(self, text):
        tokens = self.tokenizer.encode(
            text,
            disallowed_special=()
        )
        return len(tokens)

class CustomScraper:
    def __init__(self, data_source_config: DataSourceConfig):
        self.data_source_config = data_source_config
        self.load_urls = RecursiveUrlLoader(url=self.data_source_config.target_url)
    def load(self) -> Iterator[Document]:
        documents =  self.load_urls.load()
        return [Document(page_content=doc.page_content, metadata=doc.metadata) for doc in documents]

class OpenAPILoader:
    def __init__(self, data_source_config: DataSourceConfig):
        self.data_source_config = data_source_config
        self.target_url = data_source_config.target_url
    def load(self) -> List[Document]:
        """Load YAML or JSON files."""
        documents = []
        file_extension = None
        for filename in os.listdir(self.target_url):
            if file_extension is None:
                if filename.endswith('.yaml'):
                    file_extension = '.yaml'
                elif filename.endswith('.json'):
                    file_extension = '.json'
                else:
                    self.data_source_config.index_agent.log_agent.print_and_log(f"Unsupported file format: {filename}")
                    continue
            elif not filename.endswith(file_extension):
                self.data_source_config.index_agent.log_agent.print_and_log(f"Inconsistent file formats in directory: {filename}")
                continue
            file_path = os.path.join(self.target_url, filename)
            with open(file_path, 'r') as file:
                if file_extension == '.yaml':
                    documents.append(yaml.safe_load(file))
                elif file_extension == '.json':
                    documents.append(json.load(file))
        return documents

# Temporary implementation 
class OpenAPIPreProcessor:
    def __init__(self, data_source_config: DataSourceConfig):
        self.data_source_config = data_source_config
        self.tiktoken_encoding_model = data_source_config.index_agent.agent_config.tiktoken_encoding_model
        self.tokenizer = tiktoken.encoding_for_model(self.tiktoken_encoding_model)

    def run(self, documents):
        documents_as_chunks = []
        text_as_chunks = []
    
        for document in documents:
            if self._tiktoken_len(document.get('content')) > 3000:
                continue
            document_chunk, text_chunk = self.append_metadata(document)
            documents_as_chunks.append(document_chunk)
            text_as_chunks.append(text_chunk.lower())
        
        print("Total pages:", len(documents))
        print("Total chunks:", len(documents_as_chunks))
        if not documents_as_chunks:
            return
        token_counts = [
            self._tiktoken_len(chunk) for chunk in text_as_chunks
        ]
        print("Min:", min(token_counts))
        print("Avg:", int(sum(token_counts) / len(token_counts)))
        print("Max:", max(token_counts))
        print("Total tokens:", int(sum(token_counts)))

        return text_as_chunks, documents_as_chunks
    
    def append_metadata(self, document):

        # Document chunks are the metadata uploaded to vectorstore
        document_chunk = {
                    "content": document.get('content'), 
                    "url": document.get('metadata').get('doc_url'),
                    "title": document.get('metadata').get('operation_id'),
                    "resource_name": self.data_source_config.resource_name,
                    "target_type": self.data_source_config.target_type,
                    "doc_type": self.data_source_config.doc_type
                    }

        return document_chunk, document.get('content')
    
    def _tiktoken_len(self, text):
        tokens = self.tokenizer.encode(
            text,
            disallowed_special=()
        )
        return len(tokens)
        