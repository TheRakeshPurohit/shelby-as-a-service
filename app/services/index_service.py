# region Imports
import os, shutil, traceback, sys
from typing import List, Union, Iterator
import re, string, yaml, json
from urllib.parse import urlparse
import pinecone, tiktoken
from langchain.schema import Document
from langchain.document_loaders import GitbookLoader, SitemapLoader, RecursiveUrlLoader
from langchain.text_splitter import BalancedRecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from services.pinecone_io_pinecone_text.sparse import BM25Encoder
from services.log_service import Logger

from services.open_api_minifier_service import OpenAPIMinifierService

# endregion

class IndexService:
       
    def __init__(self, deployment_instance):
        self.deployment_name = deployment_instance.deployment_name
        self.secrets = deployment_instance.secrets
        self.config = deployment_instance.index_config
        self.log = Logger(self.deployment_name, f"{self.deployment_name}_index_agent", f"{self.deployment_name}_index_agent.md", level="INFO")

        self.index_env = deployment_instance.index_env
        self.index_name = deployment_instance.index_name
        self.tokenizer = tiktoken.encoding_for_model(self.config.index_tiktoken_encoding_model)

        self.prompt_template_path = "app/prompt_templates"
        self.index_dir = f"app/deployments/{self.deployment_name}/index"
        # Loads data sources from file
        with open(f"app/deployments/{self.deployment_name}/index_description.yaml", 'r', encoding="utf-8") as stream:
                self.index_description_file = yaml.safe_load(stream)
        
        if self.index_description_file['index_name'] != self.index_name:
            raise ValueError("Index name in index_description.yaml does not match index from deployment.env!")
        
        pinecone.init(
            environment=self.index_env,
            api_key=self.secrets['pinecone_api_key'], 
        )
        
        indexes = pinecone.list_indexes()
        if self.index_name not in indexes:
            # create new index
            self.create_index()
            indexes = pinecone.list_indexes()
            self.log.print_and_log(f"Created index: {indexes}")
        self.vectorstore = pinecone.Index(self.index_name)

        ### Adds sources from yaml config file to queue ###
        
        self.enabled_data_sources = []
        # Iterate over each source aka namespace
        for domain in self.index_description_file["data_domains"]:
            data_domain_name = domain['name']
            domain_description = domain['description']
            for data_source_name, source in domain['sources'].items():
                    data_source = DataSourceConfig(self, data_domain_name, domain_description, data_source_name, source)
                    if data_source.update_enabled == False:
                        continue
                    self.enabled_data_sources.append(data_source)
                    self.log.print_and_log(f'Will index: {data_source_name}')
                    
                
    def ingest_docs(self):
        
        self.log.print_and_log(f'Initial index stats: {self.vectorstore.describe_index_stats()}\n')
        
        for data_source in self.enabled_data_sources:
            # Retries if there is an error
            retry_count = 2
            for i in range(retry_count):
                try: 
                    self.log.print_and_log(f'-----Now indexing: {data_source.data_source_name}\n')
                    # Get count of vectors in index matching the "resource" metadata field
                    index_resource_stats = data_source.vectorstore.describe_index_stats(
                        filter={
                            'data_source_name': {"$eq": data_source.data_source_name}
                            }
                        )
                    existing_resource_vector_count = index_resource_stats.get('namespaces', {}).get(self.deployment_name, {}).get('vector_count', 0)
                    self.log.print_and_log(f"Existing vector count for {data_source.data_source_name}: {existing_resource_vector_count}")
                    
                    # Load documents
                    documents = data_source.scraper.load()
                    self.log.print_and_log(f'Total documents loaded for indexing: {len(documents)}')
                    if not documents:
                        self.log.print_and_log(f'Skipping data_source: no data loaded for {data_source.data_source_name}')
                        break
                    
    
                    # Removes bad chars, and chunks text
                    document_chunks = data_source.preprocessor.run(documents)
                    self.log.print_and_log(f'Total document chunks after processing: {len(document_chunks)}')
                    
                    # Checks against local docs if there are changes or new docs
                    has_changes, new_or_changed_chunks = data_source.preprocessor.compare_chunks(data_source, document_chunks)
                    # If there are changes or new docs, delete existing local files and write new files
                    if not has_changes:
                        self.log.print_and_log(f'Skipping data_source: no new data found for {data_source.data_source_name}')
                        break
                    self.log.print_and_log(f'Found {len(new_or_changed_chunks)} new or changed documents')
                    text_chunks, document_chunks = data_source.preprocessor.create_text_chunks(data_source, document_chunks)
                    self.log.print_and_log(f'Total document chunks after final check: {len(document_chunks)}')
                    
                    # Get dense_embeddings
                    dense_embeddings = data_source.embedding_retriever.embed_documents(text_chunks)

                    # Get sparse_embeddings
                    # Pretrain "corpus"
                    # data_source.bm25_encoder.fit(text_chunks)
                    # sparse_embeddings = data_source.bm25_encoder.encode_documents(text_chunks)
                    # self.log.print_and_log(f'Embeddings created. Dense: {len(dense_embeddings)} Sparse: {len(sparse_embeddings)}')
                    

                    # If the "resource" already has vectors delete the existing vectors before upserting new vectors
                    # We have to delete all because the difficulty in specifying specific documents in pinecone
                    if existing_resource_vector_count != 0:
                        self.clear_data_source(data_source)
                        index_resource_stats = data_source.vectorstore.describe_index_stats(
                        filter={
                            'data_source_name': {"$eq": data_source.data_source_name}
                            }
                        )
                        cleared_resource_vector_count = index_resource_stats.get('namespaces', {}).get(self.deployment_name, {}).get('vector_count', 0)
                        self.log.print_and_log(f'Removing pre-existing vectors. New count: {cleared_resource_vector_count} (should be 0)')
                    
                    
                    vectors_to_upsert = []
                    vector_counter = 0
                    for i, document_chunk in enumerate(document_chunks):
                        prepared_vector = {
                            "id": f"id-{data_source.data_source_name}-{vector_counter}",
                            "values": dense_embeddings[i],  
                            "metadata": document_chunk
                        }
                        # prepared_vector = {
                        #     "id": f"id-{data_source.data_source_name}-{vector_counter}",
                        #     "values": dense_embeddings[i],  
                        #     "metadata": document_chunk,  
                        #     'sparse_values': sparse_embeddings[i]
                        # }
                        vector_counter += 1
                        vectors_to_upsert.append(prepared_vector)

                    self.log.print_and_log(f'Upserting {len(vectors_to_upsert)} vectors')
                    data_source.vectorstore.upsert(
                        vectors=vectors_to_upsert,               
                        namespace=self.deployment_name,
                        batch_size=self.config.index_vectorstore_upsert_batch_size,
                        show_progress=True                 
                    )
                    
                    index_resource_stats = data_source.vectorstore.describe_index_stats(
                    filter={
                        'data_source_name': {"$eq": data_source.data_source_name}
                        }
                    )
                    new_resource_vector_count = index_resource_stats.get('namespaces', {}).get(self.deployment_name, {}).get('vector_count', 0)
                    self.log.print_and_log(f'Indexing complete for: {data_source.data_source_name}\nPrevious vector count: {existing_resource_vector_count}\nNew vector count: {new_resource_vector_count}\n')
                    # self.log.print_and_log(f'Post-upsert index stats: {index_resource_stats}\n')
                    
                    data_source.preprocessor.write_chunks(data_source, document_chunks)
                    
                    # If completed successfully, break the retry loop
                    break
                
                except Exception as error:
                    error_info = traceback.format_exc()
                    self.log.print_and_log(f"An error occurred: {error}\n{error_info}")
                    if i < retry_count - 1:  # i is zero indexed
                        continue  # this will start the next iteration of loop thus retrying your code block
                    else:
                        raise  # if exception in the last retry then raise it.
    
        self.log.print_and_log(f'Final index stats: {self.vectorstore.describe_index_stats()}')
        
    def delete_index(self):
        
        self.log.print_and_log(f"Deleting index {self.index_name}")
        stats = self.vectorstore.describe_index_stats()
        self.log.print_and_log(stats)
        pinecone.delete_index(self.index_name)
        self.log.print_and_log(self.vectorstore.describe_index_stats())

    def clear_index(self):
        self.log.print_and_log('Deleting all vectors in index.')
        stats = self.vectorstore.describe_index_stats()
        self.log.print_and_log(stats)
        for key in stats['namespaces']:
            self.vectorstore.delete(deleteAll='true', namespace=key)
        self.log.print_and_log(self.vectorstore.describe_index_stats())
    
    def clear_deplyoment(self):
        self.log.print_and_log(f'Clearing namespace aka deployment: {self.deployment_name}')
        self.vectorstore.delete(deleteAll='true', namespace=self.deployment_name)
        self.log.print_and_log(self.vectorstore.describe_index_stats())
    
    def clear_data_source(self, data_source):
        data_source.vectorstore.delete(
            namespace=self.deployment_name,
            delete_all=False, 
            filter={'data_source_name': {"$eq": data_source.data_source_name}}
        )
        
    def create_index(self):
        metadata_config = {
            "indexed": self.config.index_indexed_metadata
        }
        # Prepare log message
        log_message = (
            f"Creating new index with the following configuration:\n"
            f" - Index Name: {self.index_name}\n"
            f" - Dimension: {self.config.index_vectorstore_dimension}\n"
            f" - Metric: {self.config.index_vectorstore_metric}\n"
            f" - Pod Type: {self.config.index_vectorstore_pod_type}\n"
            f" - Metadata Config: {metadata_config}"
        )
        # Log the message
        self.log.print_and_log(log_message)
        
        pinecone.create_index(
            name=self.index_name, 
            dimension=self.config.index_vectorstore_dimension, 
            metric=self.config.index_vectorstore_metric,
            pod_type=self.config.index_vectorstore_pod_type,
            metadata_config=metadata_config
            )
        
    def tiktoken_len(self, text):
        tokens = self.tokenizer.encode(
            text,
            disallowed_special=()
        )
        return len(tokens)
        
class DataSourceConfig:
    
    ### DataSourceConfig loads all configs for all datasources ###
    
    def __init__(self, index_agent: IndexService, data_domain_name, domain_description, data_source_name, source):
        
        self.index_agent = index_agent
        self.vectorstore = index_agent.vectorstore
        self.config = index_agent.config
        self.log = index_agent.log
        self.tiktoken_len = index_agent.tiktoken_len
        
        
        # From document_sources.yaml
        self.data_domain_name: str = data_domain_name
        self.domain_description: str = domain_description
        self.data_source_name: str = data_source_name
        self.filter_url: str = source.get('filter_url')
        self.update_enabled: bool = source.get('update_enabled')
        self.load_all_paths: bool = source.get('load_all_paths')
        self.skip_paths: bool = source.get('skip_paths')
        self.target_url: str = source.get('target_url')
        self.target_type: str = source.get('target_type')
        self.doc_type: str = source.get('doc_type')
        self.api_url_format: str = source.get('api_url_format')

        # Check if any value is None
        attributes = [
            self.data_domain_name,
            self.data_source_name,
            self.update_enabled,
            self.target_url,
            self.target_type,
            self.doc_type
            ]
        if not all(attr is not None and attr != "" for attr in attributes):
            raise ValueError("Some required fields are missing or have no value.")
        
        match self.target_type:
            
            case 'gitbook':
                self.scraper = GitbookLoader(
                    web_page=self.target_url,
                    load_all_paths=self.load_all_paths,
                    skip_paths=self.skip_paths
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
            model=self.config.index_embedding_model,
            embedding_ctx_length=self.config.index_embedding_max_chunk_size,
            openai_api_key=self.index_agent.secrets['openai_api_key'],
            chunk_size=self.config.index_embedding_batch_size,
            request_timeout=self.config.index_openai_timeout_seconds
        )

        self.bm25_encoder = BM25Encoder()

class CustomPreProcessor:
    
    ### CustomPreProcessor cleans and chunks text into a format friendly to context enriched queries ###
    
    def __init__(self, data_source_config: DataSourceConfig):
        
        self.index_agent = data_source_config.index_agent
        self.config = data_source_config.index_agent.config
        self.data_source_config = data_source_config
        
        self.tiktoken_encoding_model = self.config.index_tiktoken_encoding_model
        
        self.tiktoken_len = self.index_agent.tiktoken_len

        

        self.text_splitter = BalancedRecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name=self.tiktoken_encoding_model,
            goal_length=self.config.index_text_splitter_goal_length,
            max_length=self.config.index_text_splitter_max_length,
            chunk_overlap=self.config.index_text_splitter_chunk_overlap
        )

    def run(self, documents: Union[Document, List[Document]]) -> List[Document]:
        
        processed_document_chunks = []
        processed_text_chunks = []
        
        for i, doc in enumerate(documents):
            # If no doc title use the url and the resource type
            if not doc.metadata.get('title'):
                parsed_url = urlparse(doc.metadata.get('loc'))
                _, tail = os.path.split(parsed_url.path)
                # Strip anything with "." like ".html"
                root, _ = os.path.splitext(tail)
                doc.metadata['title'] = f'{self.data_source_config.data_source_name}: {root}'
            
            # Remove bad chars and extra whitespace chars
            doc.page_content = self.strip_excess_whitespace(doc.page_content)
            doc.metadata['title'] = self.strip_excess_whitespace(doc.metadata['title'])
            
            self.index_agent.log.print_and_log(f"Doc number: {i}\n Title: {doc.metadata['title']}")
            
            # Skip if too small
            if self.tiktoken_len(doc.page_content) < self.data_source_config.config.index_preprocessor_min_length:
                self.index_agent.log.print_and_log(f'page too small: {self.tiktoken_len(doc.page_content)}')
                continue
            
            # Split into chunks
            text_chunks = self.text_splitter.split_text(doc.page_content)
            for text_chunk in text_chunks:
                document_chunk, text_chunk = self.append_metadata(text_chunk, doc)
                processed_document_chunks.append(document_chunk)
                processed_text_chunks.append(text_chunk.lower())
        
        self.index_agent.log.print_and_log(f'Total docs: {len(documents)}')
        self.index_agent.log.print_and_log(f'Total chunks: {len(processed_document_chunks)}')
        if not processed_document_chunks:
            return
        token_counts = [
            self.tiktoken_len(chunk) for chunk in processed_text_chunks
        ]
        self.index_agent.log.print_and_log(f'Min: {min(token_counts)}')
        self.index_agent.log.print_and_log(f'Avg: {int(sum(token_counts) / len(token_counts))}')
        self.index_agent.log.print_and_log(f'Max: {max(token_counts)}')
        self.index_agent.log.print_and_log(f'Total tokens: {int(sum(token_counts))}')

        return processed_document_chunks
    
    def strip_excess_whitespace(self, text):
        
        # Defines which chars can be kept; Alpha-numeric chars, punctionation, and whitespaces.
        # Remove bad chars
        text = re.sub(f'[^{re.escape(string.printable)}]', '', text)
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
    
    def remove_all_white_space_except_space(self, text):
        # Remove all whitespace characters (like \n, \r, \t, \f, \v) except space (' ')
        text = re.sub(r'[\n\r\t\f\v]+', '', text)
        # Remove any extra spaces
        text = re.sub(r' +', ' ', text)
        # Remove leading and trailing spaces
        text = text.strip()
        return text
                    
    def append_metadata(self, text_chunk, page):
        
        # Document chunks are the metadata uploaded to vectorstore
        document_chunk = {
                    "content": text_chunk, 
                    "url": page.metadata['source'].strip(), 
                    "title": page.metadata['title'],
                    "data_domain_name": self.data_source_config.data_domain_name,
                    "data_source_name": self.data_source_config.data_source_name,
                    "target_type": self.data_source_config.target_type,
                    "doc_type": self.data_source_config.doc_type
                    }
        # Text chunks here are used to create embeddings
        text_chunk =  f"{text_chunk} title: {page.metadata['title']}"

        return document_chunk, text_chunk
    
    def compare_chunks(self, data_source, document_chunks):
        
        folder_path = f'{self.index_agent.index_dir}/outputs/{data_source.data_domain_name}/{data_source.data_source_name}'
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
            if self.tiktoken_len(text_chunk) > self.config.index_text_splitter_max_length:
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

    def create_text_chunks(self, data_source, document_chunks):
        
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
            if self.tiktoken_len(text_chunk) > self.config.index_text_splitter_max_length:
                continue
            checked_document_chunks.append(document_chunk)
            checked_text_chunks.append(text_chunk.lower())
            
        return checked_text_chunks, checked_document_chunks
    
    def write_chunks(self, data_source, document_chunks):
         
        folder_path = f'{self.index_agent.index_dir}/outputs/{data_source.data_domain_name}/{data_source.data_source_name}'
        # Clear the folder first
        shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True)
        # This will keep track of the counts for each title
        title_counter = {}
        for document_chunk in document_chunks:
            sanitized_title = re.sub(r'\W+', '_', document_chunk['title'])
            text_chunk = f"{document_chunk['content']} title: {document_chunk['title']}"
            # Skip overly long chunks
            if self.tiktoken_len(text_chunk) > self.config.index_text_splitter_max_length:
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
        self.config = data_source_config
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
                    # self.data_source_config.index_agent.log_agent.print_and_log(f"Unsupported file format: {filename}")
                    continue
            elif not filename.endswith(file_extension):
                # self.data_source_config.index_agent.log_agent.print_and_log(f"Inconsistent file formats in directory: {filename}")
                continue
            file_path = os.path.join(self.data_source_config.target_url, filename)
            with open(file_path, 'r') as file:
                if file_extension == '.yaml':
                    open_api_specs.append(yaml.safe_load(file))
                elif file_extension == '.json':
                    open_api_specs.append(json.load(file))
        
        return open_api_specs
    
   
        