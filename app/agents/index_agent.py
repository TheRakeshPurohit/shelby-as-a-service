# region Imports
import os
from typing import List, Union
import re
import string
import yaml

from dotenv import load_dotenv

from langchain.schema import Document
from langchain.document_loaders import WebBaseLoader
from langchain.document_loaders.sitemap import SitemapLoader
from langchain.document_loaders import GitbookLoader
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
        self.log_agent = LoggerAgent('ShelbyAgent', 'ShelbyAgent.log', level='INFO')
        self.agent_config = AppConfig() 
        # Loads data sources from file
        with open('app/configuration/document_sources.yaml', 'r') as stream:
            try:
                self.data_source_config = yaml.safe_load(stream)
            except yaml.YAMLError as e:
                self.log_agent.print_and_log(e)

        self.document_sources_resources = []
        # Iterate over each "name"
        for source_name, resources_dict in self.data_source_config.items():
            # Then iterate over each resource for that "name"
            for resource_name, resource_content in resources_dict['resources'].items():
                try:
                    data_source = DataSourceConfig(self, source_name, resource_name, resource_content)
                    if not data_source.enabled:
                        continue
                    self.document_sources_resources.append(data_source)
                except ValueError as e:
                    self.log_agent.print_and_log(f"Error processing source {resource_name}: {e}")
                    continue
            
        self.log_agent.print_and_log(self.document_sources_resources)

    def ingest_docs(self):
        for data_source in self.document_sources_resources:
            # Load documents
            documents = data_source.scraper.load()
            if not documents:
                raise ValueError("No documents loaded.")
            text_chunks, document_chunks = data_source.preprocessor.run(documents)
            if not text_chunks:
                raise ValueError("No text_chunks loaded.")
            
            # Saves documents_chunks to folder
            os.makedirs('document_chunks', exist_ok=True)
            for i, document_chunk in enumerate(document_chunks):
                with open(os.path.join('document_chunks', f'document_chunk_{i}.md'), 'w') as f:
                    f.write(str(document_chunk))

            # Get dense_embeddings
            dense_embeddings = data_source.embedding_retriever.embed_documents(text_chunks)

            # Get sparse_embeddings
            # Pretrain "corpus"
            data_source.bm25_encoder.fit(text_chunks)
            sparse_embeddings = data_source.bm25_encoder.encode_documents(text_chunks)
            

            # Get a count of current vectors to correctly set ID
            index_stats = data_source.vectorstore.describe_index_stats()
            self.logger.debug(index_stats)

            # If namespace doesn't exist set vector count to 0
            index_vector_count = index_stats.get('namespaces', {}).get(data_source.namespace, {}).get('vector_count', 0)

            # If namespace is empty start at 0 otherwise start at count + 1
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

            self.logger.debug(f"{len(vectors_to_upsert)} chunks as vectors to upsert")
            data_source.vectorstore.upsert(
                vectors=vectors_to_upsert,               
                namespace=data_source.namespace,
                batch_size=self.agent_config.vectorstore_upsert_batch_size,
                show_progress=True                 
            )
        index_stats = data_source.vectorstore.describe_index_stats()
        self.logger.debug(index_stats)
    
    def delete_index(self):
        res = self.vectorstore.describe_index_stats()
        self.logger.debug(res)
        # res = pinecone.delete_index(data_source_config.index_name)
        # self.logger.debug(res)
        res = self.vectorstore.describe_index_stats()
        self.logger.debug(res)
    
    def clear_index(self):
        for data_source in self.document_sources_resources:
            stats = data_source.vectorstore.describe_index_stats()
            self.logger.debug(stats)
            for key in stats['namespaces']:
                data_source.vectorstore.delete(deleteAll='true', namespace=key)
            stats = data_source.vectorstore.describe_index_stats()
            self.logger.debug(stats)
    
    def clear_namespace(self):
        stats =  self.document_sources_resources[0].vectorstore.describe_index_stats()
        self.logger.debug(stats)
        self.document_sources_resources[0].vectorstore.delete(deleteAll='true', namespace=self.document_sources_resources[0].namespace)
        stats =  self.document_sources_resources[0].vectorstore.describe_index_stats()
        self.logger.debug(stats)
    
    def create_index(self, index_name, indexed_metadata):
        # pinecone.init(
        #     api_key=os.getenv("PINECONE_API_KEY"), 
        #     environment=self.vectorstore_environment
        # )
        metadata_config = {
            "indexed": indexed_metadata
        }
        # Prepare log message
        log_message = (
            f"Creating new index with the following configuration:\n"
            f" - Index Name: {index_name}\n"
            f" - Dimension: {self.agent_config.vectorstore_dimension}\n"
            f" - Metric: {self.agent_config.vectorstore_metric}\n"
            f" - Pod Type: {self.agent_config.vectorstore_pod_type}\n"
            f" - Metadata Config: {metadata_config}"
        )
        # Log the message
        self.logger.debug(log_message)
        
        return pinecone.create_index(
            name=index_name, 
            dimension=self.agent_config.vectorstore_dimension, 
            metric=self.agent_config.vectorstore_metric,
            pod_type=self.agent_config.vectorstore_pod_type,
            metadata_config=metadata_config
            )
        
class DataSourceConfig:
    def __init__(self, index_agent, source_name, resource_name, resource_content):
        
        agent_config = index_agent.agent_config
        log_agent = index_agent.log_agent
        
        # From agent_config
        self.vectorstore_environment = agent_config.vectorstore_environment
        self.index_name = agent_config.vectorstore_index
        self.indexed_metadata = agent_config.indexed_metadata
        
        # From document_sources.yaml
        self.namespace: str = source_name
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
            self.vectorstore_environment, 
            self.index_name, 
            self.namespace,
            self.enabled,
            self.load_all_paths, 
            self.target_url, 
            self.target_type, 
            self.doc_type
            ]
        if not all(attr is not None and attr != "" for attr in attributes):
            raise ValueError("Some required fields are missing or have no value.")
   
        pinecone.init(
            api_key=os.getenv("PINECONE_API_KEY"), 
            environment=self.vectorstore_environment
        )
        indexes = pinecone.list_indexes()
        log_agent.print_and_log(indexes)

        # if self.index_name not in indexes:
        #     # create new index
        #     response = index_agent.create_index(self.index_name, self.indexed_metadata)
        #     log_agent.print_and_log(f"Created index: {response}")

        # Initialize vectorstore index
        self.vectorstore = pinecone.Index(self.index_name)
        stats = self.vectorstore.describe_index_stats()
        log_agent.print_and_log(stats)

        match self.target_type:
            case 'gitbook':
                self.scraper = GitbookLoader(
                    web_page=self.target_url,
                    load_all_paths=self.load_all_paths
                    )
                self.content_type = "text"
            case 'sitemap':
                self.scraper = SitemapLoader(self.target_url,
                    filter_urls=[self.filter_url]                 
                    )
                self.content_type = "text"
            case 'local':
                self.scraper = YamlLoader('endpoint_folder/just_right')
                self.content_type = "yaml"
            # case 'code':
            #     self.preprocessor = CodePreProcessor(agent_config)
            #     self.content_type = "text"
            case _:
                raise ValueError("Invalid target type: should be gitbook, or sitemap.")
            
        match self.content_type:
            case 'text':
                self.preprocessor = CustomPreProcessor(self, log_agent, agent_config)
            case 'yaml':
                self.preprocessor = YamlPreProcessor(self, agent_config)
            # case 'html':
            #     self.preprocessor = HtmlPreProcessor(agent_config)
            # case 'code':
            #     self.preprocessor = CodePreProcessor(agent_config)
            case _:
                raise ValueError("Invalid target type: should be text, html, or code.")
            
        self.embedding_retriever = OpenAIEmbeddings(
            model=agent_config.embedding_model,
            embedding_ctx_length=agent_config.embedding_max_chunk_size,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            chunk_size=agent_config.embedding_batch_size,
            request_timeout=agent_config.openai_timeout_seconds
        )

        self.bm25_encoder = BM25Encoder()

class CustomPreProcessor:
    def __init__(self, data_source_config: DataSourceConfig, log_agent, agent_config: AppConfig):
        self.data_source_config = data_source_config
        self.agent_config = agent_config
        self.tiktoken_encoding_model=agent_config.tiktoken_encoding_model
        self.tokenizer = tiktoken.encoding_for_model(agent_config.tiktoken_encoding_model)
        self.printable = string.printable

        self.text_splitter = BalancedRecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name=self.tiktoken_encoding_model,
            goal_length=agent_config.text_splitter_goal_length,
            max_length=agent_config.text_splitter_max_length
        )

    def run(self, documents: Union[Document, List[Document]]) -> List[Document]:
        documents_as_chunks = []
        text_as_chunks = []
        for page in documents:
            if not page.metadata.get('title'):
                page.metadata['title'] = page.metadata.get('loc')
            log_agent.print_and_log(page.metadata['title'])
            # Remove bad chars
            page.page_content = re.sub(f'[^{re.escape(self.printable)}]', '', page.page_content)
            # Removes instances of more than two newlines
            page.page_content = re.sub('\n{3,}', '\n\n', page.page_content)
            # Skip if too small
            if self._tiktoken_len(page.page_content) < self.agent_config.preprocessor_min_length:
                log_agent.print_and_log("page too small")
                continue
            # Split into chunks
            text_chunks = self.text_splitter.split_text(page.page_content)
            for text_chunk in text_chunks:
                document_chunk, text_chunk = self.append_metadata(text_chunk, page)
                documents_as_chunks.append(document_chunk)
                text_as_chunks.append(text_chunk.lower())
        
        log_agent.print_and_log("Total pages:", len(documents))
        log_agent.print_and_log("Total chunks:", len(documents_as_chunks))
        if not documents_as_chunks:
            return
        token_counts = [
            self._tiktoken_len(chunk) for chunk in text_as_chunks
        ]
        log_agent.print_and_log("Min:", min(token_counts))
        log_agent.print_and_log("Avg:", int(sum(token_counts) / len(token_counts)))
        log_agent.print_and_log("Max:", max(token_counts))
        log_agent.print_and_log("Total tokens:", int(sum(token_counts)))

        return text_as_chunks, documents_as_chunks
    
    def append_metadata(self, text_chunk, page):
        # Document chunks are the metadata uploaded to vectorstore
        document_chunk = {
                    "content": text_chunk, 
                    "url": page.metadata['source'].strip(), 
                    "title": page.metadata['title'],
                    "data_source": self.data_source_config.source,
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

class YamlLoader:
    def __init__(self, directory_path: str):
        self.directory_path = directory_path
    def load(self) -> List[Document]:
        """Load YAML files."""
        documents = []
        for filename in os.listdir(self.directory_path):
            if not filename.endswith('.yaml'):  # Skip non-YAML files
                continue
            file_path = os.path.join(self.directory_path, filename)
            with open(file_path, 'r') as file:
                yaml_content = yaml.safe_load(file)
                documents.append(yaml_content)
        return documents

class YamlPreProcessor:
    def __init__(self, data_source_config: DataSourceConfig, agent_config: AppConfig):
        self.data_source_config = data_source_config
        self.agent_config = agent_config
        self.tiktoken_encoding_model=agent_config.tiktoken_encoding_model
        self.tokenizer = tiktoken.encoding_for_model(agent_config.tiktoken_encoding_model)

    def run(self, documents):
        documents_as_chunks = []
        text_as_chunks = []
    
        for document in documents:
            document_chunk, text_chunk = self.append_metadata(document)
            documents_as_chunks.append(document_chunk)
            text_as_chunks.append(text_chunk.lower())
        
        log_agent.print_and_log("Total pages:", len(documents))
        log_agent.print_and_log("Total chunks:", len(documents_as_chunks))
        if not documents_as_chunks:
            return
        token_counts = [
            self._tiktoken_len(chunk) for chunk in text_as_chunks
        ]
        log_agent.print_and_log("Min:", min(token_counts))
        log_agent.print_and_log("Avg:", int(sum(token_counts) / len(token_counts)))
        log_agent.print_and_log("Max:", max(token_counts))
        log_agent.print_and_log("Total tokens:", int(sum(token_counts)))

        return text_as_chunks, documents_as_chunks
    
    def append_metadata(self, yaml_content):
        # Use yaml.dump to convert the dictionary back to a YAML-formatted string
        yaml_string = yaml.dump(yaml_content)
        # Document chunks are the metadata uploaded to vectorstore
        document_chunk = {
                    "content": yaml_string, 
                    "url": yaml_content.get('apiDocUrl'),
                    "title": yaml_content.get('operationId'),
                    "data_source": self.data_source_config.source,
                    "target_type": self.data_source_config.target_type,
                    "doc_type": self.data_source_config.doc_type
                    }
        # Text chunks here are used to create embeddings
        text_chunk = yaml_string

        return document_chunk, text_chunk

    
    def _tiktoken_len(self, text):
        tokens = self.tokenizer.encode(
            text,
            disallowed_special=()
        )
        return len(tokens)

# main()