import os
import json
import openai
import logging
import traceback
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pydantic import ValidationError
from logger import setup_logger
import pinecone
from dotenv import load_dotenv
import tiktoken
import re
from configuration.shelby_agent_config import AppConfig
from langchain.embeddings import OpenAIEmbeddings
import yaml
from pinecone_text.sparse import BM25Encoder

class ShelbyAgent:
    def __init__(self):
        load_dotenv()
        self.template_dir = 'app/prompt_templates/'
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.logger = setup_logger('ShelbyAgent', 'ShelbyAgent.log', level=logging.DEBUG)
        self.agent_config = AppConfig() 

    # Gets embeddings from query string
    def get_query_embeddings(self, query):
        try:
            embedding_retriever = OpenAIEmbeddings(
                model=self.agent_config.llm_model,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                request_timeout=self.agent_config.openai_timeout_seconds
            )
            dense_embedding = embedding_retriever.embed_query(query)


            bm25_encoder = BM25Encoder()
            bm25_encoder.fit(query)
            sparse_embedding = bm25_encoder.encode_documents(query)

            return dense_embedding, sparse_embedding
        except Exception as e:
            self.logger.error(f"An error occurred in get_query_embeddings: {str(e)}")
            raise e

    def query_vectorstore(self, dense_embedding, sparse_embedding):
        try:
            pinecone.init(api_key=os.getenv("PINECONE_API_KEY"), environment=self.agent_config.vectorstore_environment)
            index = pinecone.Index(self.agent_config.vectorstore_index)
            
            soft_query_response = index.query(
                top_k=self.agent_config.vectorstore_top_k,
                include_values=False,
                namespace=self.agent_config.vectorstore_namespace,
                include_metadata=True,
                filter={"doc_type": {"$eq": "soft"}},
                vector=dense_embedding,
                sparse_vector=sparse_embedding
            )
            hard_query_response = index.query(
                top_k=2,
                include_values=False,
                namespace=self.agent_config.vectorstore_namespace,
                include_metadata=True,
                filter={"doc_type": {"$eq": "hard"}},
                vector=dense_embedding,
                sparse_vector=sparse_embedding
            )

            # Destructures the QueryResponse object the pinecone library generates.
            documents_list = []
            for m in soft_query_response.matches:
                self.logger.debug(m.metadata['title'])
                response = {
                    'content': m.metadata['content'],
                    'title': m.metadata['title'],
                    'url': m.metadata['url'],
                    'doc_type': m.metadata['doc_type'],
                    'score': m.score,
                    'id': m.id
                }
                documents_list.append(response)
            for m in hard_query_response.matches:
                self.logger.debug(m.metadata['title'])
                response = {
                    'content': m.metadata['content'],
                    'title': m.metadata['title'],
                    'url': m.metadata['url'],
                    'doc_type': m.metadata['doc_type'],
                    'score': m.score,
                    'id': m.id
                }
                documents_list.append(response)

            return documents_list
        except Exception as e:
            self.logger.error(f"An error occurred in query_vectorstore: {str(e)}")
            raise e
    
    # Parses documents into x and prunes the count to meet token threshold
    def parse_documents(self, returned_documents):
        try:
            def docs_tiktoken_len(documents):
                tokenizer = tiktoken.encoding_for_model(self.agent_config.llm_model)
                token_count = 0
                for doc in documents:
                    tokens = 0
                    tokens += len(tokenizer.encode(
                        doc['content'],
                        disallowed_special=()
                    ))
                    token_count += tokens
                return token_count
            
             # Count the number of 'hard' and 'soft' documents
            hard_count = sum(1 for doc in returned_documents if doc['doc_type'] == 'hard')
            soft_count = sum(1 for doc in returned_documents if doc['doc_type'] == 'soft')

            # Sort the list by score
            sorted_documents = sorted(returned_documents, key=lambda x: x['score'], reverse=True)

            # Add doc_num field
            embeddings_tokens = 0
            for i, document in enumerate(sorted_documents, start=1):
                document['doc_num'] = i

            embeddings_tokens = docs_tiktoken_len(sorted_documents)
            self.logger.info(f"embedding docs token count: {embeddings_tokens}")
            iterations = 0
            while embeddings_tokens > self.agent_config.max_docs_tokens:
                if iterations > len(sorted_documents):
                    self.logger.debug(f"Could not reduce tokens under {self.agent_configf.max_docs_tokens}.")
                    break
                # Remove the lowest scoring 'soft' document if there is more than one,
                # otherwise remove the lowest scoring 'hard' document
                if soft_count > 1:
                    for idx, document in reversed(list(enumerate(sorted_documents))):
                        if document['doc_type'] == 'soft':
                            sorted_documents.pop(idx)
                            soft_count -= 1
                            break
                elif hard_count > 1:
                    for idx, document in reversed(list(enumerate(sorted_documents))):
                        if document['doc_type'] == 'hard':
                            sorted_documents.pop(idx)
                            hard_count -= 1
                            break
                embeddings_tokens = docs_tiktoken_len(sorted_documents)
                self.logger.debug("removed lowest scoring embedding doc.")
                self.logger.info(f"embedding docs token count: {embeddings_tokens}")
                iterations += 1
            self.logger.debug(f"number of embedding docs now: {len(sorted_documents)}")
            for i, document in enumerate(sorted_documents, start=1):
                document['doc_num'] = i
            return sorted_documents
        except Exception as e:
            self.logger.error(f"An error occurred in parse_documents: {str(e)}")
            raise e

    # Generates multi-line text string with complete prompt
    # Remove new lines to optimize? 
    def load_prompt_template(self, query, documents):
        try:
            with open(os.path.join(self.template_dir, self.agent_config.prompt_template_name), 'r') as stream:
                # Load the YAML data and print the result
                prompt_template = yaml.safe_load(stream)

            # Loop over documents and append them to each other and then adds the query
            content_strs = []
            for doc in documents:
                doc_num = doc['doc_num']
                content_strs.append(f"{doc['content']} doc_num: [{doc_num}]")
                documents_str = " ".join(content_strs)
            prompt_message  = "Query: " + query + " Documents: " + documents_str

            # Loop over the list of dictionaries in data['prompt_template']
            for role in prompt_template:
                if role['role'] == 'user':  # If the 'role' is 'user'
                    role['content'] = prompt_message  # Replace the 'content' with 'prompt_message'
            
            return prompt_template
        except Exception as e:
            self.logger.error(f"An error occurred in load_prompt_template: {str(e)}")
            raise e
    
    # Need error catching here
    def prompt_llm(self, prompt):
        try:
            response = openai.ChatCompletion.create(
                model=self.agent_config.llm_model,
                messages=prompt,
            )
            return response['choices'][0]['message']['content']
        except Exception as e:
            self.logger.error(f"An error occurred in prompt_llm: {str(e)}")
            raise e

    def append_meta(self, input_text, parsed_documents):
        try:
            # Covering LLM doc notations cases
            # The modified pattern now includes optional opening parentheses or brackets before "Document"
            # and optional closing parentheses or brackets after the number
            pattern = r"[\[\(]?Document\s*\[?(\d+)\]?\)?[\]\)]?"
            formatted_text = re.sub(pattern, r"[\1]", input_text, flags=re.IGNORECASE)

            # This finds all instances of [n] in the LLM response
            pattern_num = r"\[\d\]"
            matches = re.findall(pattern_num, formatted_text)
            print(matches)

            if not matches:
                self.logger.debug("No supporting docs.")
                answer_obj = {
                    "answer_text": input_text,
                    "llm": self.agent_config.llm_model,
                    "documents": []
                }
                return answer_obj
            print(matches)

            # Formatted text has all mutations of documents n replaced with [n]
            answer_obj = {
                    "answer_text": formatted_text,
                    "llm": self.agent_config.llm_model,
                    "documents": []
            }

            if matches:
                # Creates a lit of each unique mention of [n] in LLM response
                unique_doc_nums = set([int(match[1:-1]) for match in matches])
                for doc_num in unique_doc_nums:
                    # doc_num given to llm has an index starting a 1
                    # Subtract 1 to get the correct index in the list
                    doc_index = doc_num - 1
                    # Access the document from the list using the index
                    if 0 <= doc_index < len(parsed_documents):
                        document = {
                            "doc_num": parsed_documents[doc_index]['doc_num'],
                            "url": parsed_documents[doc_index]['url'],
                            "title": parsed_documents[doc_index]['title']
                        }
                        answer_obj["documents"].append(document)
                    else:
                        self.logger.debug(f"Document{doc_num} not found in the list.")
            return answer_obj
        except Exception as e:
            self.logger.error(f"An error occurred in append_meta: {str(e)}")
            raise e
    
    def query_thread(self, query):
        try:
            self.logger.debug(f"new query:", query)
            dense_embedding, sparse_embedding = self.get_query_embeddings(query)
            self.logger.debug("embedding retrieved")
            returned_documents = self.query_vectorstore(dense_embedding, sparse_embedding)

            if not returned_documents:
                self.logger.debug("No supporting documents found!")
            else:
                self.logger.debug(f"{len(returned_documents)} documents retrieved")
            parsed_documents = self.parse_documents(returned_documents)
            prompt = self.load_prompt_template(query, parsed_documents)
            self.logger.debug("prepared prompt: %s", json.dumps(prompt, indent=4))
            self.logger.debug("sending prompt to llm")
            llm_response = self.prompt_llm(prompt)
            self.logger.debug(llm_response)
            response = self.append_meta(llm_response, parsed_documents)
            self.logger.debug("full response: %s", response)
            
            return response
        
        except Exception as e:
            raise e
     
    async def run_query(self, query):
        try:
            with ThreadPoolExecutor() as executor:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(executor, self.query_thread, query)
                return response
        except Exception as e:
            tb = traceback.format_exc()
            self.logger.error(f"An error occurred: {str(e)}. Traceback: {tb}")
            raise e

# class DocsAsker:

# class OpenAPICaller:
