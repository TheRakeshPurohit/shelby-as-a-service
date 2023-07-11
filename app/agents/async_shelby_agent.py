#region
import os
import json
import openai
import traceback
import asyncio
import yaml
from concurrent.futures import ThreadPoolExecutor
import re
from dotenv import load_dotenv
import tiktoken
from langchain.embeddings import OpenAIEmbeddings
import pinecone
from pinecone_text.sparse import BM25Encoder
from agents.logger_agent import LoggerAgent
from configuration.shelby_agent_config import AppConfig
#endregion

class ShelbyAgent:
    def __init__(self, deployment_target):
        load_dotenv()
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.log_agent = LoggerAgent('ShelbyAgent', 'ShelbyAgent.log', level='INFO')
        self.agent_config = AppConfig(deployment_target) 
        self.action_agent = self.ActionAgent(self.log_agent, self.agent_config)
        self.query_agent = self.QueryAgent(self.log_agent, self.agent_config)
        self.API_agent = self.APIAgent(self.log_agent, self.agent_config)

    def request_thread(self, request):
        # ActionAgent determines the workflow
        
        # workflow = self.action_agent.action_decision(request)
        # Currently disabled and locked to QueryAgent
        workflow = 1
        
        match workflow:
            case 1:
                # Run QueryAgent
                # If only one topic, then we skip the ActionAgent topic decision.
                if len(self.agent_config.vectorstore_namespaces) == 1:
                    topic = next(iter(self.agent_config.vectorstore_namespaces))
                else: 
                    topic = self.action_agent.topic_decision(request)
                if topic == 0:
                    # If no topic run basic query
                    # response = self.query_agent.run_basic_query(request)
                    no_topics = "Query not related to any supported topics. Supported topics are:\n"
                    for key, value in self.agent_config.vectorstore_namespaces.items():
                        no_topics += f"{key}: {value}\n"
                    self.log_agent.print_and_log(no_topics)
                    response = no_topics
                else:
                    response = self.query_agent.run_context_enriched_query(request, topic)
                
            case 2:
                # Run APIAgent
                response= self.API_agent.run_API_agent(request)
            # Else just run the docs agent for now
            case _:
                no_workflow = 'No workflow found for request.'
                self.log_agent.print_and_log(no_workflow)
                return no_workflow

        return response

    async def run_request(self, request):
        try:
            with ThreadPoolExecutor() as executor:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(executor, self.request_thread, request)
                return response
        except Exception as e:
            tb = traceback.format_exc()
            self.log_agent.print_and_log(f"An error occurred: {str(e)}. Traceback: {tb}")
            raise e

    class ActionAgent:
        def __init__(self, log_agent, agent_config):
            self.log_agent = log_agent
            self.agent_config = agent_config
    
        # Chooses workflow
        # Currently disabled
        def action_prompt_template(self, query):
            try:
                with open(os.path.join(self.agent_config.prompt_template_path, 'action_agent_action_prompt_template.yaml'), 'r') as stream:
                    # Load the YAML data and print the result
                    prompt_template = yaml.safe_load(stream)

                # Loop over the list of dictionaries in data['prompt_template']
                for role in prompt_template:
                    if role['role'] == 'user':  # If the 'role' is 'user'
                        role['content'] = query  # Replace the 'content' with 'prompt_message'
                
                return prompt_template
            except Exception as e:
                self.log_agent.print_and_log(f"An error occurred in docs_prompt_template: {str(e)}")
                raise e
            
        def action_prompt_llm(self, prompt, actions):
            try:
                # Shamelessly copied from https://github.com/minimaxir/simpleaichat/blob/main/PROMPTS.md#tools
                # Creates a dic of tokens equivalent to 0-n where n is the number of action items with a logit bias of 100
                # This forces GPT to choose one.
                logit_bias_weight = 100
                logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(actions) + 1)}

                response = openai.ChatCompletion.create(
                    model=self.agent_config.action_llm_model,
                    messages=prompt,
                    max_tokens=1,
                    logit_bias=logit_bias
                )
                return response['choices'][0]['message']['content']
            except Exception as e:
                self.log_agent.print_and_log(f"An error occurred in action_prompt_llm: {str(e)}")
                raise e
            
        def action_decision(self, query):
            prompt_template = self.action_prompt_template(query)
            actions = ['questions_on_docs', 'function_calling']
            workflow = self.action_prompt_llm(prompt_template, actions)
            return workflow 
        
        # Chooses topic
        # If no matching topic found, returns 0.
        def topic_prompt_template(self, query):

            with open(os.path.join(self.agent_config.prompt_template_path, 'action_agent_topic_prompt_template.yaml'), 'r') as stream:
                prompt_template = yaml.safe_load(stream)

           # Create a list of formatted strings, each with the format "index. key: value"
            if isinstance(self.agent_config.vectorstore_namespaces, dict):
                content_strs = [f"{index + 1}. {key}: {value}" for index, (key, value) in enumerate(self.agent_config.vectorstore_namespaces.items())]
            else:
                self.log_agent.print_and_log(f"An error occured accessing vectorstore_namespaces {self.agent_config.vectorstore_namespaces}")


            # Join the strings together with spaces between them
            topics_str = " ".join(content_strs)

            # Append the documents string to the query
            prompt_message  = "user query: " + query + " topics: " + topics_str
            
            # Loop over the list of dictionaries in data['prompt_template']
            for role in prompt_template:
                if role['role'] == 'user':  
                    role['content'] = prompt_message  
            
            return prompt_template
    
        def topic_prompt_llm(self, prompt):

            # Shamelessly copied from https://github.com/minimaxir/simpleaichat/blob/main/PROMPTS.md#tools
            # Creates a dic of tokens equivalent to 0-n where n is the number of topics with a logit bias of 100
            # This forces GPT to choose one.
            logit_bias_weight = 100
            logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(self.agent_config.vectorstore_namespaces) + 1)}

            response = openai.ChatCompletion.create(
                model=self.agent_config.action_llm_model,
                messages=prompt,
                max_tokens=1,
                logit_bias=logit_bias
            )
            try:
                topic_key = int(response['choices'][0]['message']['content'])
            except ValueError:
                # This block will execute if the conversion to int fails.
                self.log_agent.print_and_log(f"Failed to convert topic_key to int: {response['choices'][0]['message']['content']}")
                return 0
            if topic_key == 0:
                return 0
            # Otherwise return string with the namespace of the topic in the vectorstore
            topic = list(self.agent_config.vectorstore_namespaces.keys())[topic_key - 1]  # We subtract 1 because list indices start at 0
            return topic
            
        def topic_decision(self, query):
            prompt_template = self.topic_prompt_template(query)
            topic = self.topic_prompt_llm(prompt_template)
            
            self.log_agent.print_and_log(f"{self.agent_config.action_llm_model} chose to fetch context docs from {topic} namespace.")
            
            return topic 

    class QueryAgent:
        def __init__(self, log_agent, agent_config):
            self.log_agent = log_agent
            self.agent_config = agent_config

        # Gets embeddings from query string
        def get_query_embeddings(self, query):
            try:
                
                self.log_agent.print_and_log(f"embedding query: {query}")
                
                embedding_retriever = OpenAIEmbeddings(
                    model=self.agent_config.query_llm_model,
                    openai_api_key=os.getenv("OPENAI_API_KEY"),
                    request_timeout=self.agent_config.openai_timeout_seconds
                )
                dense_embedding = embedding_retriever.embed_query(query)


                bm25_encoder = BM25Encoder()
                bm25_encoder.fit(query)
                sparse_embedding = bm25_encoder.encode_documents(query)

                return dense_embedding, sparse_embedding
            except Exception as e:
                self.log_agent.print_and_log(f"An error occurred in get_query_embeddings: {str(e)}")
                raise e

        def query_vectorstore(self, dense_embedding, sparse_embedding, topic):
            try:
                pinecone.init(api_key=os.getenv("PINECONE_API_KEY"), environment=self.agent_config.vectorstore_environment)
                index = pinecone.Index(self.agent_config.vectorstore_index)
                
                soft_query_response = index.query(
                    top_k=self.agent_config.vectorstore_top_k,
                    include_values=False,
                    namespace=topic,
                    include_metadata=True,
                    filter={"doc_type": {"$eq": "soft"}},
                    vector=dense_embedding,
                    sparse_vector=sparse_embedding
                )
                hard_query_response = index.query(
                    top_k=self.agent_config.vectorstore_top_k,
                    include_values=False,
                    namespace=topic,
                    include_metadata=True,
                    filter={"doc_type": {"$eq": "hard"}},
                    vector=dense_embedding,
                    sparse_vector=sparse_embedding
                )

                # Destructures the QueryResponse object the pinecone library generates.
                documents_list = []
                for m in soft_query_response.matches:
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
                self.log_agent.print_and_log(f"An error occurred in query_vectorstore: {str(e)}")
                raise e
        
        # Parses documents into x and prunes the count to meet token threshold
        def parse_documents(self, returned_documents):
            try:
                def docs_tiktoken_len(documents):
                    tokenizer = tiktoken.encoding_for_model(self.agent_config.tiktoken_encoding_model)
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
                
                # self.log_agent.print_and_log(f"context docs token count: {embeddings_tokens}")
                iterations = 0
                while embeddings_tokens > self.agent_config.max_docs_tokens:
                    if iterations > len(sorted_documents):
                        self.log_agent.print_and_log(f"Could not reduce tokens under {self.agent_config.max_docs_tokens}.")
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
                    # self.log_agent.print_and_log("removed lowest scoring embedding doc .")
                    # self.log_agent.print_and_log(f"context docs token count: {embeddings_tokens}")
                    iterations += 1
                # self.log_agent.print_and_log(f"number of context docs now: {len(sorted_documents)}")
                # Same as above but removes based on total count of docs instead of token count.
                while len(sorted_documents) > self.agent_config.max_docs_used:
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
                    # self.log_agent.print_and_log("removed lowest scoring embedding doc.")

                self.log_agent.print_and_log(f"final number of context docs now: {len(sorted_documents)}")
                
                for i, document in enumerate(sorted_documents, start=1):
                    document['doc_num'] = i
                return sorted_documents
            except Exception as e:
                self.log_agent.print_and_log(f"An error occurred in parse_documents: {str(e)}")
                raise e
    
        # Generates multi-line text string with complete prompt
        def docs_prompt_template(self, query, documents):
            try:
                with open(os.path.join(self.agent_config.prompt_template_path, 'query_agent_prompt_template.yaml'), 'r') as stream:
                    # Load the YAML data and print the result
                    prompt_template = yaml.safe_load(stream)

                # Loop over documents and append them to each other and then adds the query
                if documents:
                    content_strs = []
                    for doc in documents:
                        doc_num = doc['doc_num']
                        content_strs.append(f"{doc['content']} doc_num: [{doc_num}]")
                        documents_str = " ".join(content_strs)
                    prompt_message  = "Query: " + query + " Documents: " + documents_str
                else:
                    prompt_message  = "Query: " + query

                # Loop over the list of dictionaries in data['prompt_template']
                for role in prompt_template:
                    if role['role'] == 'user':  # If the 'role' is 'user'
                        role['content'] = prompt_message  # Replace the 'content' with 'prompt_message'
                        
                # self.log_agent.print_and_log(f"prepared prompt: {json.dumps(prompt_template, indent=4)}")
                
                return prompt_template
            
            except Exception as e:
                self.log_agent.print_and_log(f"An error occurred in docs_prompt_template: {str(e)}")
                raise e
        
        def docs_prompt_llm(self, prompt):
            try:
                self.log_agent.print_and_log(f"sending prompt to llm")
                
                response = openai.ChatCompletion.create(
                    model=self.agent_config.query_llm_model,
                    messages=prompt,
                    max_tokens=self.agent_config.max_response_tokens
                )
                
                # self.log_agent.print_and_log(response['choices'][0]['message']['content'])
                
                return response['choices'][0]['message']['content']
            
            except Exception as e:
                self.log_agent.print_and_log(f"An error occurred in docs_prompt_llm: {str(e)}")
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
                    self.log_agent.print_and_log("No supporting docs.")
                    answer_obj = {
                        "answer_text": input_text,
                        "llm": self.agent_config.query_llm_model,
                        "documents": []
                    }
                    return answer_obj
                print(matches)

                # Formatted text has all mutations of documents n replaced with [n]
                answer_obj = {
                        "answer_text": formatted_text,
                        "llm": self.agent_config.query_llm_model,
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
                            self.log_agent.print_and_log(f"Document{doc_num} not found in the list.")
                            
                # self.log_agent.print_and_log(f"response with metadata: {answer_obj}")
                
                return answer_obj
            
            except Exception as e:
                self.log_agent.print_and_log(f"An error occurred in append_meta: {str(e)}")
                raise e
    
        def run_context_enriched_query(self, query, topic):
            
            dense_embedding, sparse_embedding = self.get_query_embeddings(query)
            returned_documents = self.query_vectorstore(dense_embedding, sparse_embedding, topic)

            if not returned_documents:
                self.log_agent.print_and_log("No supporting documents found!")
            else:
                self.log_agent.print_and_log(f"{len(returned_documents)} context docs retrieved")
                
            parsed_documents = self.parse_documents(returned_documents)
            
            prompt = self.docs_prompt_template(query, parsed_documents)
            self.log_agent.print_and_log(f'Sending prompt: {prompt}')
            llm_response = self.docs_prompt_llm(prompt)
            self.log_agent.print_and_log(f'LLM response: {llm_response}')
            
            response = self.append_meta(llm_response, parsed_documents)
            
            return response
    
    # Currently under development
    class APIAgent:
        def __init__(self, log_agent, agent_config):
            self.log_agent = log_agent
            self.agent_config = agent_config
        
        # Selects the correct API and endpoint to run action on.
        # Eventually, we should create a merged file that describes all available API.
        def select_API_operationID(self, query):
            API_spec_path = self.agent_config.API_spec_path
            # Load prompt template to be used with all APIs
            with open(os.path.join(self.agent_config.prompt_template_path, 'API_agent_select_operationID_prompt_template.yaml'), 'r') as stream:
                # Load the YAML data and print the result
                prompt_template = yaml.safe_load(stream)
            operationID_file = None
            # Iterates all OpenAPI specs in API_spec_path directory,
            # and asks LLM if the API can satsify the request and if so which document to return
            for entry in os.scandir(API_spec_path):
                if entry.is_dir():
                    # Create prompt
                    with open(os.path.join(entry.path, 'LLM_OAS_keypoint_guide_file.txt'), 'r') as stream:
                        keypoint = yaml.safe_load(stream)
                        prompt_message  = "query: " + query + " spec: " + keypoint
                        for role in prompt_template:
                            if role['role'] == 'user': 
                                role['content'] = prompt_message  
                        # Creates a dic of tokens that are the only acceptable answers
                        # This forces GPT to choose one.
                        logit_bias = {
                            # 0-9
                            "15": 100,
                            "16": 100,
                            "17": 100,
                            "18": 100,
                            "19": 100,
                            "20": 100,
                            "21": 100,
                            "22": 100,
                            "23": 100,
                            "24": 100,
                            # \n
                            "198": 100,
                            # x
                            "87": 100,
                        }
                        response = openai.ChatCompletion.create(
                            model=self.agent_config.select_operationID_llm_model,
                            messages=prompt_template,
                            # 5 tokens when doc_number == 999
                            max_tokens=5,
                            logit_bias=logit_bias,
                            stop='x'
                        )
                answer = response['choices'][0]['message']['content']
                # need to check if there are no numbers in answer
                if 'x' in answer or answer == '':
                    # Continue until you find a good operationID.
                    continue
                else:
                    digits = answer.split('\n')  
                    number_str = ''.join(digits)  
                    number = int(number_str)  
                    directory_path = f"data/minified_openAPI_specs/{entry.name}/operationIDs/"
                    for filename in os.listdir(directory_path):
                        if filename.endswith(f"-{number}.json"):
                            with open(os.path.join(directory_path, filename), 'r') as f:
                                operationID_file = json.load(f)
                            self.log_agent.print_and_log(f"operationID_file found: {os.path.join(directory_path, filename)}.")
                            break
                    break
            if operationID_file is None:
                self.log_agent.print_and_log("No matching operationID found.")
            return operationID_file
                
        def create_bodyless_function(self, query, operationID_file):
            with open(os.path.join(self.agent_config.prompt_template_path, 'API_agent_create_bodyless_function_prompt_template.yaml'), 'r') as stream:
                # Load the YAML data and print the result
                prompt_template = yaml.safe_load(stream)
                
            prompt_message  = "user_request: " + query 
            prompt_message  += f"\nurl: " + operationID_file['metadata']['server_url'] + " operationid: " + operationID_file['metadata']['operation_id']
            prompt_message  += f"\nspec: " + operationID_file['context']
            for role in prompt_template:
                if role['role'] == 'user': 
                    role['content'] = prompt_message 
                    
            response = openai.ChatCompletion.create(
                            model=self.agent_config.create_function_llm_model,
                            messages=prompt_template,
                            max_tokens=500,
                        )
            url_maybe  = response['choices'][0]['message']['content']
            return url_maybe
  
                    
        def run_API_agent(self, query):
            self.log_agent.print_and_log(f"new action: {query}")
            operationID_file = self.select_API_operationID(query)
            # Here we need to run a doc_agent query if operationID_file is None
            function = self.create_bodyless_function(query, operationID_file)
            # Here we need to run a doc_agent query if url_maybe does not parse as a url
            
            # Here we need to run a doc_agent query if the function doesn't run correctly
            
            # Here we send the request to GPT to evaluate the answer
            

            return response
    

