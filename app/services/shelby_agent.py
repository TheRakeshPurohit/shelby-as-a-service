#region
import os, asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import json, yaml, re
import openai, pinecone, tiktoken
from typing import Optional
from langchain.embeddings import OpenAIEmbeddings
from pinecone_text.sparse import BM25Encoder
from services.base_class import BaseClass
#endregion

class ShelbyAgent(BaseClass):
    
    #region
    ### You probably don't need to change anything here ###
    # ActionAgent
    action_llm_model: str = 'gpt-4'
    # QueryAgent
    pre_query_llm_model: str = 'gpt-4'
    max_doc_token_length: int = 1200
    embedding_model: str = 'text-embedding-ada-002'
    tiktoken_encoding_model: str = 'text-embedding-ada-002'
    # pre_query_llm_model: str = 'gpt-3.5-turbo'
    query_llm_model: str = 'gpt-4'
    vectorstore_top_k: int = 5
    max_docs_tokens: int = 3500
    max_docs_used: int = 5
    max_response_tokens: int = 300
    openai_timeout_seconds: float = 180.0
    # APIAgent
    select_operationID_llm_model: str = 'gpt-4'
    create_function_llm_model: str = 'gpt-4'
    populate_function_llm_model: str = 'gpt-4'

    # vectorstore_namespaces = {key: value['description'] for key, value in BaseClass.data_sources.items()}    
    #endregion
    
    def __init__(self, sprite, **kwargs):
        super().__init__(**kwargs)  
        self.LoadVarsFromEnv()
        self.check_shelby_agent_config()
        
        # self.log_service = LogService(f'{moniker}_{platform}_ShelbyAgent', f'{moniker}_{platform}_ShelbyAgent.log', level='INFO')
        # self.config.load_shelby_agent_config()
        # self.action_agent = ActionAgent(self, self.config)
        # self.query_agent = QueryAgent(self, self.config)
        # self.API_agent = APIAgent(self, self.config)
        openai.api_key = self.openai_api_key

    def request_thread(self, request):
        
        try:
            # ActionAgent determines the workflow
            # workflow = self.action_agent.action_decision(request)
            # Currently disabled and locked to QueryAgent
            workflow = 1
            match workflow:
                case 1:
                    # Run QueryAgent
                    if len(self.config.vectorstore_namespaces) == 1:
                        # If only one topic, then we skip the ActionAgent topic decision.
                        topic = next(iter(self.config.vectorstore_namespaces))
                    else: 
                        topic = self.action_agent.topic_decision(request)
                    if topic == 0:
                        # If no topics found message is sent to sprite
                        no_topics = "Query not related to any supported topics. Supported topics are:\n"
                        for key, value in self.config.vectorstore_namespaces.items():
                            no_topics += f"{key}: {value}\n"
                        # self.log_service.print_and_log(no_topics)
                        response = no_topics
                    else:
                        response = self.query_agent.run_context_enriched_query(request, topic)
                case 2:
                    # Run APIAgent
                    response= self.API_agent.run_API_agent(request)
                case _:
                    # Else just run the docs agent for now
                    no_workflow = 'No workflow found for request.'
                    # self.log_service.print_and_log(no_workflow)
                    return no_workflow
                
            return response
        
        except Exception as e:
            # Logs error and sends error to sprite
            error_message = f"An error occurred while processing request: {e}\n"
            error_message += "Traceback (most recent call last):\n"
            error_message += traceback.format_exc()

            # self.log_service.print_and_log(error_message)
           
            return f"Bot broke. Probably just an API issue. Feel free to try again. Otherwise contact support."

    async def run_request(self, request):
        
        # Required to run multiple requests at a time in async
        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(executor, self.request_thread, request)
            
            return response
        
    def check_response(self, response):
        # Check if keys exist in dictionary
        parsed_respoonse = response.get('choices', [{}])[0].get('message', {}).get('content')
        
        if not parsed_respoonse:
            # self.log_service.print_and_log(f'Error in response: {response}')
            return None
        
        return parsed_respoonse
    
    def check_shelby_agent_config(self):
        pass 
    
# class ActionAgent:
    
#     ### ActionAgent orchestrates the path requests flow through workflows ###
    
#     def __init__(self, shelby_agent, log_service, config):
        
#         self.shelby_agent = shelby_agent
#         # self.log_service = log_service
#         self.config = config

#     def action_prompt_template(self, query):
        
#         # Chooses workflow
#         # Currently disabled
#         with open(os.path.join('app/prompt_templates/', 'action_agent_action_prompt_template.yaml'), 'r') as stream:
#             # Load the YAML data and print the result
#             prompt_template = yaml.safe_load(stream)

#         # Loop over the list of dictionaries in data['prompt_template']
#         for role in prompt_template:
#             if role['role'] == 'user':  # If the 'role' is 'user'
#                 role['content'] = query  # Replace the 'content' with 'prompt_message'
        
#         return prompt_template
    
#     def action_prompt_llm(self, prompt, actions):

#         # Shamelessly copied from https://github.com/minimaxir/simpleaichat/blob/main/PROMPTS.md#tools
#         # Creates a dic of tokens equivalent to 0-n where n is the number of action items with a logit bias of 100
#         # This forces GPT to choose one.
#         logit_bias_weight = 100
#         logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(actions) + 1)}

#         response = openai.ChatCompletion.create(
#             model=self.config.action_llm_model,
#             messages=prompt,
#             max_tokens=1,
#             logit_bias=logit_bias
#         )
        
#         return response['choices'][0]['message']['content']
        
#     def action_decision(self, query):
        
#         prompt_template = self.action_prompt_template(query)
#         actions = ['questions_on_docs', 'function_calling']
#         workflow = self.action_prompt_llm(prompt_template, actions)
#         return workflow 
    
#     def topic_prompt_template(self, query):
        
#         # Chooses topic
#         # If no matching topic found, returns 0.
#         with open(os.path.join('app/prompt_templates/', 'action_agent_topic_prompt_template.yaml'), 'r') as stream:
#             prompt_template = yaml.safe_load(stream)

#         # Create a list of formatted strings, each with the format "index. key: value"
#         if isinstance(self.config.vectorstore_namespaces, dict):
#             content_strs = [f"{index + 1}. {key}: {value}" for index, (key, value) in enumerate(self.config.vectorstore_namespaces.items())]

#         # Join the strings together with spaces between them
#         topics_str = " ".join(content_strs)

#         # Append the documents string to the query
#         prompt_message  = "user query: " + query + " topics: " + topics_str
        
#         # Loop over the list of dictionaries in data['prompt_template']
#         for role in prompt_template:
#             if role['role'] == 'user':  
#                 role['content'] = prompt_message  
        
#         return prompt_template

#     def topic_prompt_llm(self, prompt):

#         logit_bias_weight = 100
#         logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(self.config.vectorstore_namespaces) + 1)}

#         response = openai.ChatCompletion.create(
#             model=self.config.action_llm_model,
#             messages=prompt,
#             max_tokens=1,
#             logit_bias=logit_bias
#         )
        
#         topic_response = self.shelby_agent.check_response(response)
#         if not topic_response:
#             return None

#         topic_key = int(topic_response)

#         if topic_key == 0:
#             return 0
#         # Otherwise return string with the namespace of the topic in the vectorstore
#         topic = list(self.config.vectorstore_namespaces.keys())[topic_key - 1]  # We subtract 1 because list indices start at 0
        
#         return topic
        
#     def topic_decision(self, query):
        
#         prompt_template = self.topic_prompt_template(query)
#         topic = self.topic_prompt_llm(prompt_template)
        
#         # self.log_service.print_and_log(f"{self.config.action_llm_model} chose to fetch context docs from {topic} namespace.")
        
#         return topic 

# class QueryAgent:
    
#     ### QueryAgent answers questions ###
    
#     def __init__(self, shelby_agent, log_service, config):
        
#         self.shelby_agent = shelby_agent
#         # self.log_service = log_service
#         self.config = config

#     def pre_query(self, query):
        
#         with open(os.path.join('app/prompt_templates/', 'query_agent_pre_query_template.yaml'), 'r') as stream:
#             # Load the YAML data and print the result
#             prompt_template = yaml.safe_load(stream)
            
#         # Loop over the list of dictionaries in data['prompt_template']
#         for role in prompt_template:
#             if role['role'] == 'user':  # If the 'role' is 'user'
#                 role['content'] = query  # Replace the 'content' with 'prompt_message'
                
#         response = openai.ChatCompletion.create(
#             model=self.config.pre_query_llm_model,
#             messages=prompt_template,
#             max_tokens=25
#         )
        
#         pre_query_response = self.shelby_agent.check_response(response)
#         if not pre_query_response:
#             return None

#         pre_query = f'query: {query}, keywords: {pre_query_response}'
        
#         return pre_query
    
#     def get_query_embeddings(self, query):
            
#         embedding_retriever = OpenAIEmbeddings(
#             model=self.config.embedding_model,
#             openai_api_key=self.config.openai_api_key,
#             request_timeout=self.config.openai_timeout_seconds
#         )
#         dense_embedding = embedding_retriever.embed_query(query)


#         bm25_encoder = BM25Encoder()
#         bm25_encoder.fit(query)
#         sparse_embedding = bm25_encoder.encode_documents(query)

#         return dense_embedding, sparse_embedding

#     def query_vectorstore(self, dense_embedding, sparse_embedding, topic):
            
#         pinecone.init(api_key=self.config.pinecone_api_key, environment=self.config.vectorstore_environment)
#         index = pinecone.Index(self.config.vectorstore_index)
        
#         soft_query_response = index.query(
#             top_k=self.config.vectorstore_top_k,
#             include_values=False,
#             namespace=topic,
#             include_metadata=True,
#             filter={"doc_type": {"$eq": "soft"}},
#             vector=dense_embedding,
#             sparse_vector=sparse_embedding
#         )
#         hard_query_response = index.query(
#             top_k=self.config.vectorstore_top_k,
#             include_values=False,
#             namespace=topic,
#             include_metadata=True,
#             filter={"doc_type": {"$eq": "hard"}},
#             vector=dense_embedding,
#             sparse_vector=sparse_embedding
#         )

#         # Destructures the QueryResponse object the pinecone library generates.
#         returned_documents = []
#         for m in soft_query_response.matches:
#             response = {
#                 'content': m.metadata['content'],
#                 'title': m.metadata['title'],
#                 'url': m.metadata['url'],
#                 'doc_type': m.metadata['doc_type'],
#                 'score': m.score,
#                 'id': m.id
#             }
#             returned_documents.append(response)
#         for m in hard_query_response.matches:
#             response = {
#                 'content': m.metadata['content'],
#                 'title': m.metadata['title'],
#                 'url': m.metadata['url'],
#                 'doc_type': m.metadata['doc_type'],
#                 'score': m.score,
#                 'id': m.id
#             }
#             returned_documents.append(response)
                            
#         return returned_documents

#     def doc_check(self, query, documents):
        
#         with open(os.path.join('app/prompt_templates/', 'query_agent_doc_check_template.yaml'), 'r') as stream:
#             # Load the YAML data and print the result
#             prompt_template = yaml.safe_load(stream)
        
#         doc_counter = 1
#         content_strs = []
#         for doc in documents:
#             content_strs.append(f"{doc['title']} doc_number: [{doc_counter}]")
#             documents_str = " ".join(content_strs)
#             doc_counter += 1
#         prompt_message  = "Query: " + query + " Documents: " + documents_str
        
#         logit_bias_weight = 100
#         # 0-9
#         logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(documents) + 1)}             
#         # \n
#         logit_bias["198"] = logit_bias_weight
 
#         # Loop over the list of dictionaries in data['prompt_template']
#         for role in prompt_template:
#             if role['role'] == 'user':  # If the 'role' is 'user'
#                 role['content'] = prompt_message  # Replace the 'content' with 'prompt_message'
                
#         response = openai.ChatCompletion.create(
#             model=self.config.pre_query_llm_model,
#             messages=prompt_template,
#             max_tokens=10,
#             logit_bias=logit_bias
#         )

#         doc_check = self.shelby_agent.check_response(response)
#         if not doc_check:
#             return None
        
#         # This finds all instances of n in the LLM response
#         pattern_num = r"\d"
#         matches = re.findall(pattern_num, doc_check)

#         if (len(matches) == 1 and matches[0] == '0') or len(matches) == 0:
#             # self.log_service.print_and_log(f'Error in doc_check: {response}')
#             return None

#         relevant_documents = []
#         # Creates a list of each unique mention of n in LLM response
#         unique_doc_nums = set([int(match) for match in matches])
#         for doc_num in unique_doc_nums:
#             # doc_num given to llm has an index starting a 1
#             # Subtract 1 to get the correct index in the list
#             # Access the document from the list using the index
#             relevant_documents.append(documents[doc_num - 1])

#         return relevant_documents

#     def parse_documents(self, returned_documents):

#         def _tiktoken_len(document):
#             tokenizer = tiktoken.encoding_for_model(self.config.tiktoken_encoding_model)
#             tokens = tokenizer.encode(
#                 document,
#                 disallowed_special=()
#             )
#             return len(tokens)
        
#         def _docs_tiktoken_len(documents):
#             tokenizer = tiktoken.encoding_for_model(self.config.tiktoken_encoding_model)
#             token_count = 0
#             for document in documents:
#                 tokens = 0
#                 tokens += len(tokenizer.encode(
#                     document['content'],
#                     disallowed_special=()
#                 ))
#                 token_count += tokens
#             return token_count
        
#         # Count the number of 'hard' and 'soft' documents
#         hard_count = sum(1 for doc in returned_documents if doc['doc_type'] == 'hard')
#         soft_count = sum(1 for doc in returned_documents if doc['doc_type'] == 'soft')

#         # Sort the list by score
#         sorted_documents = sorted(returned_documents, key=lambda x: x['score'], reverse=True)

#         for i, document in enumerate(sorted_documents, start=1):
#             token_count = _tiktoken_len(document['content'])
#             if token_count > self.config.max_docs_tokens:
#                 sorted_documents.pop(idx)
#                 continue
#             document['token_count'] = token_count
#             document['doc_num'] = i
        
#         embeddings_tokens = _docs_tiktoken_len(sorted_documents)
        
#         self.log_service.print_and_log(f"context docs token count: {embeddings_tokens}")
#         iterations = 0
#         original_documents_count = len(sorted_documents)
#         while embeddings_tokens > self.config.max_docs_tokens:
#             if iterations >= original_documents_count:
#                 break
#             # Find the index of the document with the highest token_count that exceeds max_doc_token_length
#             max_token_count_idx = max((idx for idx, document in enumerate(sorted_documents) if document['token_count'] > self.config.max_doc_token_length), 
#                     key=lambda idx: sorted_documents[idx]['token_count'], default=None)
#             # If a document was found that meets the conditions, remove it from the list
#             if max_token_count_idx is not None:
#                 doc_type = sorted_documents[max_token_count_idx]['doc_type']
#                 if doc_type == 'soft':
#                     soft_count -= 1
#                 else:
#                     hard_count -= 1
#                 sorted_documents.pop(max_token_count_idx)
#                 break
#             # Remove the lowest scoring 'soft' document if there is more than one,
#             elif soft_count > 1:
#                 for idx, document in reversed(list(enumerate(sorted_documents))):
#                     if document['doc_type'] == 'soft':
#                         sorted_documents.pop(idx)
#                         soft_count -= 1
#                         break
#             # otherwise remove the lowest scoring 'hard' document
#             elif hard_count > 1:
#                 for idx, document in reversed(list(enumerate(sorted_documents))):
#                     if document['doc_type'] == 'hard':
#                         sorted_documents.pop(idx)
#                         hard_count -= 1
#                         break
#             else:
#                 # Find the index of the document with the highest token_count
#                 max_token_count_idx = max(range(len(sorted_documents)), key=lambda idx: sorted_documents[idx]['token_count'])
#                 # Remove the document with the highest token_count from the list
#                 sorted_documents.pop(max_token_count_idx)

#             embeddings_tokens = _docs_tiktoken_len(sorted_documents)
#             self.log_service.print_and_log("removed lowest scoring embedding doc .")
#             self.log_service.print_and_log(f"context docs token count: {embeddings_tokens}")
#             iterations += 1
#         self.log_service.print_and_log(f"number of context docs now: {len(sorted_documents)}")
#         # Same as above but removes based on total count of docs instead of token count.
#         while len(sorted_documents) > self.config.max_docs_used:
#             if soft_count > 1:
#                 for idx, document in reversed(list(enumerate(sorted_documents))):
#                     if document['doc_type'] == 'soft':
#                         sorted_documents.pop(idx)
#                         soft_count -= 1
#                         break
#             elif hard_count > 1:
#                 for idx, document in reversed(list(enumerate(sorted_documents))):
#                     if document['doc_type'] == 'hard':
#                         sorted_documents.pop(idx)
#                         hard_count -= 1
#                         break
#             self.log_service.print_and_log("removed lowest scoring embedding doc.")
                            
#         for i, document in enumerate(sorted_documents, start=1):
#             document['doc_num'] = i
        
#         return sorted_documents

#     def docs_prompt_template(self, query, documents):

#         with open(os.path.join('app/prompt_templates/', 'query_agent_prompt_template.yaml'), 'r') as stream:
#             # Load the YAML data and print the result
#             prompt_template = yaml.safe_load(stream)

#         # Loop over documents and append them to each other and then adds the query
#         if documents:
#             content_strs = []
#             for doc in documents:
#                 doc_num = doc['doc_num']
#                 content_strs.append(f"{doc['content']} doc_num: [{doc_num}]")
#                 documents_str = " ".join(content_strs)
#             prompt_message  = "Query: " + query + " Documents: " + documents_str
#         else:
#             prompt_message  = "Query: " + query

#         # Loop over the list of dictionaries in data['prompt_template']
#         for role in prompt_template:
#             if role['role'] == 'user':  # If the 'role' is 'user'
#                 role['content'] = prompt_message  # Replace the 'content' with 'prompt_message'
                
#         self.log_service.print_and_log(f"prepared prompt: {json.dumps(prompt_template, indent=4)}")
        
#         return prompt_template

#     def docs_prompt_llm(self, prompt):
        
#         response = openai.ChatCompletion.create(
#             model=self.config.query_llm_model,
#             messages=prompt,
#             max_tokens=self.config.max_response_tokens
#         )
#         prompt_response = self.shelby_agent.check_response(response)
#         if not prompt_response:
#             return None
        
#         return prompt_response
        
#     def append_meta(self, input_text, parsed_documents):

#         # Covering LLM doc notations cases
#         # The modified pattern now includes optional opening parentheses or brackets before "Document"
#         # and optional closing parentheses or brackets after the number
#         pattern = r"[\[\(]?Document\s*\[?(\d+)\]?\)?[\]\)]?"
#         formatted_text = re.sub(pattern, r"[\1]", input_text, flags=re.IGNORECASE)

#         # This finds all instances of [n] in the LLM response
#         pattern_num = r"\[\d\]"
#         matches = re.findall(pattern_num, formatted_text)
#         print(matches)

#         if not matches:
#             # self.log_service.print_and_log("No supporting docs.")
#             answer_obj = {
#                 "answer_text": input_text,
#                 "llm": self.config.query_llm_model,
#                 "documents": []
#             }
#             return answer_obj
#         print(matches)

#         # Formatted text has all mutations of documents n replaced with [n]
#         answer_obj = {
#                 "answer_text": formatted_text,
#                 "llm": self.config.query_llm_model,
#                 "documents": []
#         }

#         if matches:
#             # Creates a lit of each unique mention of [n] in LLM response
#             unique_doc_nums = set([int(match[1:-1]) for match in matches])
#             for doc_num in unique_doc_nums:
#                 # doc_num given to llm has an index starting a 1
#                 # Subtract 1 to get the correct index in the list
#                 doc_index = doc_num - 1
#                 # Access the document from the list using the index
#                 if 0 <= doc_index < len(parsed_documents):
#                     document = {
#                         "doc_num": parsed_documents[doc_index]['doc_num'],
#                         "url": parsed_documents[doc_index]['url'],
#                         "title": parsed_documents[doc_index]['title']
#                     }
#                     answer_obj["documents"].append(document)
#                 else:
#                     # self.log_service.print_and_log(f"Document{doc_num} not found in the list.")
                    
#         # self.log_service.print_and_log(f"response with metadata: {answer_obj}")
        
#         return answer_obj

#     def run_context_enriched_query(self, query, topic):
        
#         # self.log_service.print_and_log(f'Running query: {query}')
        
#         pre_query = self.pre_query(query)
#         # self.log_service.print_and_log(f"Pre-query response: {pre_query}")
        
#         dense_embedding, sparse_embedding = self.get_query_embeddings(pre_query)
#         # self.log_service.print_and_log("Sparse and dense embeddings retrieved")
        
#         returned_documents = self.query_vectorstore(dense_embedding, sparse_embedding, topic)
#         if not returned_documents:
#             # self.log_service.print_and_log("No supporting documents found!")
#         returned_documents_list = []
#         for returned_doc in returned_documents:
#             returned_documents_list.append(returned_doc['url'])
#         # self.log_service.print_and_log(f"{len(returned_documents)} documents returned from vectorstore: {returned_documents_list}")
        
#         returned_documents = self.doc_check(query, returned_documents)
#         if not returned_documents:
#             # self.log_service.print_and_log("No supporting documents after doc_check!")
#         returned_documents_list = []
#         for returned_doc in returned_documents:
#             returned_documents_list.append(returned_doc['url'])
#         # self.log_service.print_and_log(f"{len(returned_documents)} documents returned from doc_check: {returned_documents_list}")
        
#         parsed_documents = self.parse_documents(returned_documents)
#         final_documents_list = []
#         for parsed_document in parsed_documents:
#             final_documents_list.append(parsed_document['url'])
#         # self.log_service.print_and_log(f"{len(parsed_documents)} documents returned after parsing: {final_documents_list}")
            
#         prompt = self.docs_prompt_template(query, parsed_documents)
        
#         # self.log_service.print_and_log(f'Sending prompt to LLM')
#         llm_response = self.docs_prompt_llm(prompt)
#         # self.log_service.print_and_log(f'LLM response: {llm_response}')
                
#         parsed_response = self.append_meta(llm_response, parsed_documents)
#         # self.log_service.print_and_log(f'LLM response with appended metadata: {parsed_response}')
        
#         return parsed_response

# # class APIAgent:
        
# #         ### APIAgent makes API calls on behalf the user ###
# #         # Currently under development
        
# #         def __init__(self, shelby_agent, log_service, config):
            
# #             self.shelby_agent = shelby_agent
# #             # self.log_service = log_service
# #             self.config = config
        
# #         # Selects the correct API and endpoint to run action on.
# #         # Eventually, we should create a merged file that describes all available API.
# #         def select_API_operationID(self, query):
            
# #             API_spec_path = self.config.API_spec_path
# #             # Load prompt template to be used with all APIs
# #             with open(os.path.join('app/prompt_templates/', 'API_agent_select_operationID_prompt_template.yaml'), 'r') as stream:
# #                 # Load the YAML data and print the result
# #                 prompt_template = yaml.safe_load(stream)
# #             operationID_file = None
# #             # Iterates all OpenAPI specs in API_spec_path directory,
# #             # and asks LLM if the API can satsify the request and if so which document to return
# #             for entry in os.scandir(API_spec_path):
# #                 if entry.is_dir():
# #                     # Create prompt
# #                     with open(os.path.join(entry.path, 'LLM_OAS_keypoint_guide_file.txt'), 'r') as stream:
# #                         keypoint = yaml.safe_load(stream)
# #                         prompt_message  = "query: " + query + " spec: " + keypoint
# #                         for role in prompt_template:
# #                             if role['role'] == 'user': 
# #                                 role['content'] = prompt_message  
                                
# #                         logit_bias_weight = 100
# #                         # 0-9
# #                         logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + 5 + 1)}             
# #                         # \n
# #                         logit_bias["198"] = logit_bias_weight
# #                         # x
# #                         logit_bias["87"] = logit_bias_weight
 
# #                         # Creates a dic of tokens that are the only acceptable answers
# #                         # This forces GPT to choose one.
                  
# #                         response = openai.ChatCompletion.create(
# #                             model=self.config.select_operationID_llm_model,
# #                             messages=prompt_template,
# #                             # 5 tokens when doc_number == 999
# #                             max_tokens=5,
# #                             logit_bias=logit_bias,
# #                             stop='x'
# #                         )
# #                 operation_response = self.shelby_agent.check_response(response)
# #                 if not operation_response:
# #                     return None
        
# #                 # need to check if there are no numbers in answer
# #                 if 'x' in operation_response or operation_response == '':
# #                     # Continue until you find a good operationID.
# #                     continue
# #                 else:
# #                     digits = operation_response.split('\n')  
# #                     number_str = ''.join(digits)  
# #                     number = int(number_str)  
# #                     directory_path = f"data/minified_openAPI_specs/{entry.name}/operationIDs/"
# #                     for filename in os.listdir(directory_path):
# #                         if filename.endswith(f"-{number}.json"):
# #                             with open(os.path.join(directory_path, filename), 'r') as f:
# #                                 operationID_file = json.load(f)
# #                             # self.log_service.print_and_log(f"operationID_file found: {os.path.join(directory_path, filename)}.")
# #                             break
# #                     break
# #             if operationID_file is None:
# #                 # self.log_service.print_and_log("No matching operationID found.")
            
# #             return operationID_file
                
# #         def create_bodyless_function(self, query, operationID_file):
            
# #             with open(os.path.join('app/prompt_templates/', 'API_agent_create_bodyless_function_prompt_template.yaml'), 'r') as stream:
# #                 # Load the YAML data and print the result
# #                 prompt_template = yaml.safe_load(stream)
                
# #             prompt_message  = "user_request: " + query 
# #             prompt_message  += f"\nurl: " + operationID_file['metadata']['server_url'] + " operationid: " + operationID_file['metadata']['operation_id']
# #             prompt_message  += f"\nspec: " + operationID_file['context']
# #             for role in prompt_template:
# #                 if role['role'] == 'user': 
# #                     role['content'] = prompt_message 
                    
# #             response = openai.ChatCompletion.create(
# #                             model=self.config.create_function_llm_model,
# #                             messages=prompt_template,
# #                             max_tokens=500,
# #                         )
# #             url_response = self.shelby_agent.check_response(response)
# #             if not url_response:
# #                 return None
                
# #             return url_response
             
# #         def run_API_agent(self, query):
            
# #             # self.log_service.print_and_log(f"new action: {query}")
# #             operationID_file = self.select_API_operationID(query)
# #             # Here we need to run a doc_agent query if operationID_file is None
# #             function = self.create_bodyless_function(query, operationID_file)
# #             # Here we need to run a doc_agent query if url_maybe does not parse as a url
            
# #             # Here we need to run a doc_agent query if the function doesn't run correctly
            
# #             # Here we send the request to GPT to evaluate the answer
            
# #             return response
    


        
       