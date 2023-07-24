# region Imports
import os, shutil, traceback
from typing import List, Union, Iterator
import re, string, yaml, json
from urllib.parse import urlparse


import pinecone, tiktoken


from langchain.schema import Document
from langchain.document_loaders import GitbookLoader, SitemapLoader, RecursiveUrlLoader
from langchain.text_splitter import BalancedRecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from pinecone_text.sparse import BM25Encoder

from .log_service import LogService

from .open_api_minifier_service import OpenAPIMinifierService

# endregion

class IndexService:
    
    ### IndexAgent loads configs and data sources ###
    # IndexAgent
    embedding_model: str = "text-embedding-ada-002"
    embedding_max_chunk_size: int = 8191
    embedding_batch_size: int = 100
    vectorstore_dimension: int = 1536
    vectorstore_upsert_batch_size: int = 20
    vectorstore_metric: str = "dotproduct"
    vectorstore_pod_type: str = "p1"
    preprocessor_min_length: int = 100
    text_splitter_goal_length: int = 1500
    text_splitter_max_length: int = 2000
    text_splitter_chunk_overlap: int = 100
    indexed_metadata: list[str] = ["data_source", "doc_type", "target_type", "resource_name"]
        
    def __init__(self):
        
        try:

            self.log_agent = LogService('IndexAgent', 'IndexAgent.log', level='INFO')
            self.agent_config = AppConfig(self.log_agent) 
            self.tokenizer = tiktoken.encoding_for_model(self.agent_config.tiktoken_encoding_model)
            
            # Loads data sources from file
            with open(self.agent_config.document_sources_filepath, 'r') as stream:
                    self.data_source_config = yaml.safe_load(stream)
                    
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
 
            ### Adds sources from yaml config file to queue ###
            
            self.document_sources_resources = []
            # Iterate over each source aka namespace
            for namespace, resources_dict in self.data_source_config.items():
                # Then iterate over each resource within a source
                for resource_name, resource_content in resources_dict['resources'].items():
                    data_source = DataSourceConfig(self, namespace, resource_name, resource_content)
                    if data_source.enabled == False:
                        continue
                    self.document_sources_resources.append(data_source)
                    self.log_agent.print_and_log(f'Will index: {resource_name}')
                
        except Exception as e:
            # Logs error and sends error to sprite
            error_info = traceback.format_exc()
            self.log_agent.print_and_log(f"An error occurred: {e}\n{error_info}")
        
            pass
             
    def ingest_docs(self):
        
        self.log_agent.print_and_log(f'Initial index stats: {self.vectorstore.describe_index_stats()}\n')
        
        for data_resource in self.document_sources_resources:
            # Retries if there is an error
            retry_count = 2
            for i in range(retry_count):
                try: 
                    self.log_agent.print_and_log(f'Now indexing: {data_resource.resource_name}\n')
                    # Load documents
                    documents = data_resource.scraper.load()
                    
                    self.log_agent.print_and_log(f'Total documents loaded for indexing: {len(documents)}')
                    
                    if not documents:
                        self.log_agent.print_and_log(f'Skipping data_resource: no data loaded for {data_resource.resource_name}')
                        break
                    
                    # Removes bad chars, and chunks text
                    document_chunks = data_resource.preprocessor.run(documents)
                    self.log_agent.print_and_log(f'Total document chunks after processing: {len(document_chunks)}')
                    
                    # Checks against local docs if there are changes or new docs
                    has_changes, new_or_changed_chunks = data_resource.preprocessor.compare_chunks(data_resource, document_chunks)
                    
                    text_chunks, document_chunks = data_resource.preprocessor.create_text_chunks(data_resource, document_chunks)
                    self.log_agent.print_and_log(f'Total document chunks after final check: {len(document_chunks)}')
                    
                    # If there are changes or new docs, delete existing local files and write new files
                    if not has_changes:
                        self.log_agent.print_and_log(f'Skipping data_resource: no new data found for {data_resource.resource_name}')
                        break
                    self.log_agent.print_and_log(f'Found {len(new_or_changed_chunks)} new or changed documents')

                    # Get count of vectors in index matching the "resource" metadata field
                    index_resource_stats = data_resource.vectorstore.describe_index_stats(filter={'resource_name': data_resource.resource_name})
                    existing_resource_vector_count = index_resource_stats.get('namespaces', {}).get(data_resource.namespace, {}).get('vector_count', 0)
                    self.log_agent.print_and_log(f"Existing vector count for {data_resource.resource_name}: {existing_resource_vector_count}")
                    
                    self.log_agent.print_and_log(f'Pre-change index stats: {self.vectorstore.describe_index_stats()}\n')
                    
                    # If the "resource" already has vectors delete the existing vectors before upserting new vectors
                    # We have to delete all because the difficulty in specifying specific documents in pinecone
                    if existing_resource_vector_count != 0:
                        cleared_resource_vector_count = self.clear_resource_name(data_resource).get('namespaces', {}).get(data_resource.namespace, {}).get('vector_count', 0)
                        self.log_agent.print_and_log(f'Removing pre-existing vectors. New count: {cleared_resource_vector_count} (should be 0)')
                        
                    # Get dense_embeddings
                    dense_embeddings = data_resource.embedding_retriever.embed_documents(text_chunks)

                    # Get sparse_embeddings
                    # Pretrain "corpus"
                    data_resource.bm25_encoder.fit(text_chunks)
                    sparse_embeddings = data_resource.bm25_encoder.encode_documents(text_chunks)
                    self.log_agent.print_and_log(f'Embeddings created. Dense: {len(dense_embeddings)} Sparse: {len(sparse_embeddings)}')
                    
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

                    self.log_agent.print_and_log(f'Upserting {len(vectors_to_upsert)} vectors')
                    data_resource.vectorstore.upsert(
                        vectors=vectors_to_upsert,               
                        namespace=data_resource.namespace,
                        batch_size=self.agent_config.vectorstore_upsert_batch_size,
                        show_progress=True                 
                    )
                    
                    index_resource_stats = data_resource.vectorstore.describe_index_stats(filter={'resource_name': data_resource.resource_name})
                    self.log_agent.print_and_log(f'Post-upsert index stats: {index_resource_stats}\n')
                    new_resource_vector_count = index_resource_stats.get('namespaces', {}).get(data_resource.namespace, {}).get('vector_count', 0)
                    self.log_agent.print_and_log(f'Indexing complete for: {data_resource.resource_name}\nPrevious vector count: {existing_resource_vector_count}\nNew vector count: {new_resource_vector_count}\n')
                    
                    data_resource.preprocessor.write_chunks(data_resource, document_chunks)
                    
                    # If completed successfully, break the retry loop
                    break
                
                except Exception as e:
                    error_info = traceback.format_exc()
                    self.log_agent.print_and_log(f"An error occurred: {e}\n{error_info}")
                    if i < retry_count - 1:  # i is zero indexed
                        continue  # this will start the next iteration of loop thus retrying your code block
                    else:
                        raise  # if exception in the last retry then raise it.
    
        self.log_agent.print_and_log(f'Final index stats: {self.vectorstore.describe_index_stats()}')
        
    def delete_index(self):
        
        res = self.document_sources_resources[0].vectorstore.describe_index_stats()
        self.log_agent.print_and_log(res)
        res = pinecone.delete_index(self.agent_config.vectorstore_index)
        self.log_agent.print_and_log(res)
        res = self.document_sources_resources[0].vectorstore.describe_index_stats()
        self.log_agent.print_and_log(res)
        
        return res

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
        return data_resource.vectorstore.describe_index_stats(filter={'resource_name': data_resource.resource_name})
        
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
    
    def tiktoken_len(self, text):
        tokens = self.tokenizer.encode(
            text,
            disallowed_special=()
        )
        return len(tokens)
        
class DataSourceConfig:
    
    ### DataSourceConfig loads all configs for all datasources ###
    
    def __init__(self, index_agent: IndexAgent, namespace, resource_name, resource_content):
        
        self.index_agent = index_agent
        self.agent_config = self.index_agent.agent_config
        self.log_agent = self.index_agent.log_agent
        
        self.tiktoken_len = self.index_agent.tiktoken_len
        
        self.index_name = index_agent.agent_config.vectorstore_index
        self.indexed_metadata = index_agent.agent_config.indexed_metadata
        
        self.output_folder = f'index/{namespace}/{resource_name}'
        
        # From document_sources.yaml
        self.'namespace': str = namespace
        self.resource_name: str = resource_name
        self.filter_url: str = resource_content.get('filter_url')
        self.enabled: bool = resource_content.get('enabled')
        self.load_all_paths: bool = resource_content.get('load_all_paths')
        self.target_url: str = resource_content.get('target_url')
        self.target_type: str = resource_content.get('target_type')
        self.doc_type: str = resource_content.get('doc_type')
        self.api_url_format: str = resource_content.get('api_url_format')

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
            api_key=self.agent_config.pinecone_api_key, 
            environment=self.agent_config.vectorstore_environment
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
                # May need to change for specific websites
                def parse_content_by_id(content):

                    # Attempt to find element by 'content-container' ID
                    content_element = content.find(id='content-container')
                    if not content_element:
                        # If 'content-container' not found, attempt to find 'content'
                        content_element = content.find(id='content')
                    if not content_element:
                        # If neither found, return an empty string
                        return ''
                    # Find all elements with "visibility: hidden" style and class containing "toc"
                    unwanted_elements = content_element.select('[style*="visibility: hidden"], [class*="toc"]')
                    # Remove unwanted elements from content_element
                    for element in unwanted_elements:
                        element.decompose()
                    # Remove header tags
                    for header in content_element.find_all('header'):
                        header.decompose()
                    # Extract text from the remaining content
                    text = content_element.get_text(separator=' ')

                    return text
                
                self.scraper = SitemapLoader(
                    self.target_url,
                    filter_urls=[self.filter_url],
                    parsing_function=parse_content_by_id           
                    )
                self.content_type = "text"
                
            case 'generic':
                self.scraper = CustomScraper(self)
                self.content_type = "text"
                
            case 'open_api_spec':
                self.scraper = OpenAPILoader(self)
                self.content_type = 'open_api_spec'
                
            case _:
                raise ValueError(f"Invalid target type: {self.target_type}")
            
        match self.content_type:
            case 'text':
                self.preprocessor = CustomPreProcessor(self)
            case 'open_api_spec':
                self.preprocessor = OpenAPIMinifierService(self)
            case _:
                raise ValueError("Invalid target type: should be text, html, or code.")
            
        self.embedding_retriever = OpenAIEmbeddings(
            model=self.agent_config.embedding_model,
            embedding_ctx_length=self.agent_config.embedding_max_chunk_size,
            openai_api_key=self.agent_config.openai_api_key,
            chunk_size=self.agent_config.embedding_batch_size,
            request_timeout=self.agent_config.openai_timeout_seconds
        )

        self.bm25_encoder = BM25Encoder()

class CustomPreProcessor:
    
    ### CustomPreProcessor cleans and chunks text into a format friendly to context enriched queries ###
    
    def __init__(self, data_source_config: DataSourceConfig):
        
        self.index_agent = data_source_config.index_agent
        self.agent_config = data_source_config.agent_config
        self.log_agent = data_source_config.log_agent
        self.data_source_config = data_source_config
        
        self.tiktoken_encoding_model = self.agent_config.tiktoken_encoding_model
        
        self.tiktoken_len = self.index_agent.tiktoken_len

        # Defines which chars can be kept; Alpha-numeric chars, punctionation, and whitespaces.
        self.printable = string.printable

        self.text_splitter = BalancedRecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name=self.tiktoken_encoding_model,
            goal_length=self.agent_config.text_splitter_goal_length,
            max_length=self.agent_config.text_splitter_max_length,
            chunk_overlap=self.agent_config.text_splitter_chunk_overlap
        )

    def run(self, documents: Union[Document, List[Document]]) -> List[Document]:
        
        processed_document_chunks = []
        processed_text_chunks = []
        
        for doc in documents:
            # If no doc title use the url and the resource type
            if not doc.metadata.get('title'):
                parsed_url = urlparse(doc.metadata.get('loc'))
                _, tail = os.path.split(parsed_url.path)
                # Strip anything with "." like ".html"
                root, _ = os.path.splitext(tail)
                doc.metadata['title'] = f'{self.data_source_config.resource_name}: {root}'
            
            # Remove bad chars and extra whitespace chars
            doc.page_content = self.process_text(doc.page_content)
            doc.metadata['title'] = self.process_text(doc.metadata['title'])
            
            self.data_source_config.log_agent.print_and_log(doc.metadata['title'])
            
            # Skip if too small
            if self.tiktoken_len(doc.page_content) < self.data_source_config.index_agent.agent_config.preprocessor_min_length:
                self.data_source_config.index_agent.log_agent.print_and_log(f'page too small: {self.tiktoken_len(doc.page_content)}')
                continue
            
            # Split into chunks
            text_chunks = self.text_splitter.split_text(doc.page_content)
            for text_chunk in text_chunks:
                document_chunk, text_chunk = self.append_metadata(text_chunk, doc)
                processed_document_chunks.append(document_chunk)
                processed_text_chunks.append(text_chunk.lower())
        
        self.log_agent.print_and_log(f'Total docs: {len(documents)}')
        self.log_agent.print_and_log(f'Total chunks: {len(processed_document_chunks)}')
        if not processed_document_chunks:
            return
        token_counts = [
            self.tiktoken_len(chunk) for chunk in processed_text_chunks
        ]
        self.log_agent.print_and_log(f'Min: {min(token_counts)}')
        self.log_agent.print_and_log(f'Avg: {int(sum(token_counts) / len(token_counts))}')
        self.log_agent.print_and_log(f'Max: {max(token_counts)}')
        self.log_agent.print_and_log(f'Total tokens: {int(sum(token_counts))}')

        return processed_document_chunks
    
    def process_text(self, text):
        
        # Remove bad chars
        text = re.sub(f'[^{re.escape(self.printable)}]', '', text)
        # Reduces any sequential occurrences of a specific whitespace (' \t\n\r\v\f') to just two of those specific whitespaces
        # Create a dictionary to map each whitespace character to its escape sequence (if needed)
        whitespace_characters = {
            ' ': r' ',
            '\t': r'\t',
            '\n': r'\n',
            '\r': r'\r',
            '\v': r'\v',
            '\f': r'\f',
        }
        # Replace any sequential occurrences of each whitespace characters greater than 3 with just two
        for char, escape_sequence in whitespace_characters.items():
            pattern = escape_sequence + "{3,}"
            replacement = char * 2
            text = re.sub(pattern, replacement, text)
            
        text = text.strip()
        
        return text
                    
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
    
    def compare_chunks(self, data_resource, document_chunks):
        
        folder_path = f'index/outputs/{data_resource.namespace}/{data_resource.resource_name}'
        # Create the directory if it does not exist
        os.makedirs(folder_path, exist_ok=True)
        existing_files = os.listdir(folder_path)
        has_changes = False
        # This will keep track of the counts for each title
        title_counter = {}
        # This will hold the titles of new or different chunks
        new_or_changed_chunks = []
        for document_chunk in document_chunks:
            sanitized_title = re.sub(r'\W+', '_', document_chunk['title'])
            text_chunk = f"{document_chunk['content']} title: {document_chunk['title']}"
            # Skip overly long chunks
            if self.tiktoken_len(text_chunk) > self.agent_config.text_splitter_max_length:
                continue
            # Check if we've seen this title before, if not initialize to 0
            if sanitized_title not in title_counter:
                title_counter[sanitized_title] = 0
            file_name = f'{sanitized_title}_{title_counter[sanitized_title]}.json'
            # Increment the counter for this title
            title_counter[sanitized_title] += 1
            if file_name not in existing_files:
                has_changes = True
                new_or_changed_chunks.append(document_chunk['title'])
            else:
                existing_file_path = os.path.join(folder_path, file_name)
                with open(existing_file_path, 'r') as f:
                    existing_data = json.load(f)
                    if existing_data != document_chunk:
                        has_changes = True
                        new_or_changed_chunks.append(document_chunk['title'])
                
        return has_changes, new_or_changed_chunks

    def create_text_chunks(self, data_resource, document_chunks):
        
        checked_document_chunks = []
        checked_text_chunks = []
        # This will keep track of the counts for each title
        title_counter = {}
        for document_chunk in document_chunks:
            sanitized_title = re.sub(r'\W+', '_', document_chunk['title'])
            # Check if we've seen this title before, if not initialize to 0
            if sanitized_title not in title_counter:
                title_counter[sanitized_title] = 0
            # Increment the counter for this title
            title_counter[sanitized_title] += 1
            text_chunk = f"{document_chunk['content']} title: {document_chunk['title']}"
            # Skip overly long chunks
            if self.tiktoken_len(text_chunk) > self.agent_config.text_splitter_max_length:
                continue
            checked_document_chunks.append(document_chunk)
            checked_text_chunks.append(text_chunk.lower())
            
        return checked_text_chunks, checked_document_chunks
    
    def write_chunks(self, data_resource, document_chunks):
         
        folder_path = f'index/outputs/{data_resource.namespace}/{data_resource.resource_name}'
        # Clear the folder first
        shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True)
        # This will keep track of the counts for each title
        title_counter = {}
        for document_chunk in document_chunks:
            sanitized_title = re.sub(r'\W+', '_', document_chunk['title'])
            text_chunk = f"{document_chunk['content']} title: {document_chunk['title']}"
            # Skip overly long chunks
            if self.tiktoken_len(text_chunk) > self.agent_config.text_splitter_max_length:
                continue
            # Check if we've seen this title before, if not initialize to 0
            if sanitized_title not in title_counter:
                title_counter[sanitized_title] = 0
            file_name = f'{sanitized_title}_{title_counter[sanitized_title]}.json'
            # Increment the counter for this title
            title_counter[sanitized_title] += 1
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, 'w') as f:
                json.dump(document_chunk, f, indent=4)
            
class CustomScraper:
    
    ### CustomScraper is a generic web scraper ###
    
    def __init__(self, data_source_config: DataSourceConfig):
        
        self.data_source_config = data_source_config
        self.load_urls = RecursiveUrlLoader(url=self.data_source_config.target_url)
    
    def load(self) -> Iterator[Document]:
        
        documents =  self.load_urls.load()
        
        return [Document(page_content=doc.page_content, metadata=doc.metadata) for doc in documents]

class OpenAPILoader:
    

    def __init__(self, data_source_config: DataSourceConfig):
        
        self.index_agent = data_source_config.index_agent
        self.agent_config = data_source_config.agent_config
        self.log_agent = data_source_config.log_agent
        self.data_source_config = data_source_config
    
    def load(self):
        
        open_api_specs = self.load_spec()
        
        return open_api_specs
    
    def load_spec(self):
        """Load YAML or JSON files."""
        open_api_specs = []
        file_extension = None
        for filename in os.listdir(self.data_source_config.target_url):
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
            file_path = os.path.join(self.data_source_config.target_url, filename)
            with open(file_path, 'r') as file:
                if file_extension == '.yaml':
                    open_api_specs.append(yaml.safe_load(file))
                elif file_extension == '.json':
                    open_api_specs.append(json.load(file))
        
        return open_api_specs
    
   
        