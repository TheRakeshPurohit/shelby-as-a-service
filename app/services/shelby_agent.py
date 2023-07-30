# region
import os, asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import json, yaml, re
import openai, pinecone, tiktoken
from typing import Optional
from langchain.embeddings import OpenAIEmbeddings
from deployment_configurator.deployment_instance import DeploymentInstance, MonikerInstance
from services.pinecone_io_pinecone_text.sparse import BM25Encoder
from services.log_service import Logger
# endregion

class ShelbyAgent:
 
    def __init__(self, instance: MonikerInstance):
        self.log = Logger(DeploymentInstance.deployment_name, f"{instance.moniker_name}_shelby_agent", f"{instance.moniker_name}_shelby_agent.md", level="INFO")

        self.instance = instance
        self.enabled_data_domains = instance.moniker_enabled_data_domains
        self.index_env = instance.index_env
        self.index_name = instance.index_name
        self.openai_api_key = instance.openai_api_key
        self.pinecone_api_key = instance.pinecone_api_key
        self.config = instance.discord_config['ShelbyConfig']
        self.action_agent = ActionAgent(self)
        self.rag_agent = CEQAgent(self)

    def request_thread(self, request):
        try:
            # ActionAgent determines the workflow
            # workflow = self.action_agent.action_decision(request)
            # Currently disabled and locked to QueryAgent
            workflow = 1
            match workflow:
                case 1:
                    response = self.rag_agent.run_context_enriched_query(request)
                # case 2:
                #     # Run APIAgent
                #     response = self.API_agent.run_API_agent(request)
                case _:
                    # Else just run the docs agent for now
                    no_workflow = "No workflow found for request."
                    self.log.print_and_log(no_workflow)
                    return no_workflow

            return response

        except Exception as e:
            # Logs error and sends error to sprite
            error_message = f"An error occurred while processing request: {e}\n"
            error_message += "Traceback (most recent call last):\n"
            error_message += traceback.format_exc()

            self.log.print_and_log(error_message)
            print(error_message)
            return error_message
            # return f"Bot broke. Probably just an API issue. Feel free to try again. Otherwise contact support."

    def check_response(self, response):
        # Check if keys exist in dictionary
        parsed_response = (
            response.get("choices", [{}])[0].get("message", {}).get("content")
        )
        if not parsed_response:
            self.log.print_and_log(f'Error in response: {response}')
            return None

        return parsed_response

class ActionAgent:

    ### ActionAgent orchestrates the path requests flow through workflows ###
    def __init__(self, shelby_agent):
        
        self.shelby_agent = shelby_agent
        
    def action_prompt_template(self, query):

        # Chooses workflow
        # Currently disabled
        with open(os.path.join('app/prompt_templates/', 'action_topic_constraint.yaml'), 'r', encoding="utf-8") as stream:
            # Load the YAML data and print the result
            prompt_template = yaml.safe_load(stream)

        # Loop over the list of dictionaries in data['prompt_template']
        for role in prompt_template:
            if role['role'] == 'user':  # If the 'role' is 'user'
                role['content'] = query  # Replace the 'content' with 'prompt_message'

        return prompt_template

    def action_prompt_llm(self, prompt, actions):

        # Shamelessly copied from https://github.com/minimaxir/simpleaichat/blob/main/PROMPTS.md#tools
        # Creates a dic of tokens equivalent to 0-n where n is the number of action items with a logit bias of 100
        # This forces GPT to choose one.
        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(actions) + 1)}

        response = openai.ChatCompletion.create(
            model=self.shelby_agent.config.action_llm_model,
            messages=prompt,
            max_tokens=1,
            logit_bias=logit_bias
        )

        return response['choices'][0]['message']['content']

    def action_decision(self, query):

        prompt_template = self.action_prompt_template(query)
        actions = ['questions_on_docs', 'function_calling']
        workflow = self.action_prompt_llm(prompt_template, actions)
        return workflow
    
    def data_domain_decision(self, query):

        # Chooses topic
        # If no matching topic found, returns 0.
        with open(os.path.join('app/prompt_templates/', 'action_topic_constraint.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)

        # Create a list of formatted strings, each with the format "index. key: value"
        if isinstance(self.shelby_agent.enabled_data_domains, dict):
            content_strs = [f"{index + 1}. {key}: {value}" for index, (key, value) in enumerate(self.shelby_agent.enabled_data_domains.items())]

        # Join the strings together with spaces between them
        topics_str = " ".join(content_strs)

        # Append the documents string to the query
        prompt_message  = "user query: " + query + " topics: " + topics_str

        # Loop over the list of dictionaries in data['prompt_template']
        for role in prompt_template:
            if role['role'] == 'user':
                role['content'] = prompt_message

        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(self.shelby_agent.enabled_data_domains) + 1)}

        response = openai.ChatCompletion.create(
            model=self.shelby_agent.config.ceq_data_domain_constraints_llm_model,
            messages=prompt_template,
            max_tokens=1,
            logit_bias=logit_bias
        )

        domain_response = self.shelby_agent.check_response(response)
        if not domain_response:
            return None

        domain_key = int(domain_response)

        if domain_key == 0:
            return 0
        # Otherwise return string with the namespace of the domain in the vectorstore
        data_domain_name = list(self.shelby_agent.enabled_data_domains.keys())[domain_key - 1]  # We subtract 1 because list indices start at 0

        self.shelby_agent.log.print_and_log(f"{self.shelby_agent.config.ceq_data_domain_constraints_llm_model} chose to fetch context docs from {domain} data domain.")
        
        return data_domain_name

class CEQAgent:
    ### QueryAgent answers questions ###
    
    def __init__(self, shelby_agent):
        
        self.shelby_agent = shelby_agent
        
    def select_data_domain(self, query):
        
        response = None
        
        if len(self.shelby_agent.enabled_data_domains) == 0:
            self.shelby_agent.log.print_and_log(f"Error: no enabled data domains for moniker: {self.shelby_agent.instance.moniker_name}")
            return 
        elif len(self.shelby_agent.enabled_data_domains) == 1:
            # If only one topic, then we skip the ActionAgent topic decision.
            domain = self.shelby_agent.enabled_data_domain[0]
            
        else:
            data_domain_name = self.shelby_agent.action_agent.data_domain_decision(query)
            
        # If no domain found message is sent to sprite
        if domain == 0:
            for key, value in self.shelby_agent.enabled_data_domains.items():
                self.shelby_agent.config.ceq_data_domain_none_found_message += f"{key}: {value}\n"
            self.shelby_agent.log_service.print_and_log(self.shelby_agent.config.ceq_data_domain_none_found_message)
            response = self.shelby_agent.config.ceq_data_domain_none_found_message
            
        return data_domain_name, response
            
    def keyword_generator(self, query):

        with open(os.path.join('app/prompt_templates/', 'ceq_keyword_generator.yaml.yaml'), 'r', encoding="utf-8") as stream:
            # Load the YAML data and print the result
            prompt_template = yaml.safe_load(stream)

        # Loop over the list of dictionaries in data['prompt_template']
        for role in prompt_template:
            if role['role'] == 'user':  # If the 'role' is 'user'
                role['content'] = query  # Replace the 'content' with 'prompt_message'

        response = openai.ChatCompletion.create(
            model=self.shelby_agent.config.ceq_keyword_generator_llm_model,
            messages=prompt_template,
            max_tokens=25
        )

        keyword_generator_response = self.shelby_agent.check_response(response)
        if not keyword_generator_response:
            return None

        generated_keywords = f'query: {query}, keywords: {keyword_generator_response}'

        return generated_keywords

    def get_query_embeddings(self, query):

        embedding_retriever = OpenAIEmbeddings(
            model=self.shelby_agent.config.ceq_embedding_model,
            openai_api_key=self.shelby_agent.openai_api_key,
            request_timeout=self.shelby_agent.config.openai_timeout_seconds
        )
        dense_embedding = embedding_retriever.embed_query(query)


        bm25_encoder = BM25Encoder()
        bm25_encoder.fit(query)
        sparse_embedding = bm25_encoder.encode_documents(query)

        return dense_embedding, sparse_embedding

    def query_vectorstore(self, dense_embedding, sparse_embedding, data_domain_name=None):

        pinecone.init(api_key=self.shelby_agent.pinecone_api_key, environment=self.shelby_agent.index_env)
        index = pinecone.Index(self.shelby_agent.index_name)

        if data_domain_name is not None:
            soft_filter = {
                "doc_type": {"$eq": "soft"},
                "data_domain_name": {"eq": f"{data_domain_name}"}
                }
        else:
            soft_filter = {"doc_type": {"$eq": "soft"}}
            
        if data_domain_name is not None:
            hard_filter = {
                "doc_type": {"$eq": "hard"},
                "data_domain_name": {"eq": f"{data_domain_name}"}
                }
        else:
            hard_filter = {"doc_type": {"$eq": "hard"}}
            
        
        soft_query_response = index.query(
            top_k=self.shelby_agent.config.ceq_docs_to_retrieve,
            include_values=False,
            namespace=self.shelby_agent.instance.moniker_name,
            include_metadata=True,
            filter=soft_filter,
            vector=dense_embedding,
            sparse_vector=sparse_embedding
        )
        hard_query_response = index.query(
            top_k=self.shelby_agent.config.ceq_docs_to_retrieve,
            include_values=False,
            namespace=self.shelby_agent.instance.moniker_name,
            include_metadata=True,
            filter=hard_filter,
            vector=dense_embedding,
            sparse_vector=sparse_embedding
        )

        # Destructures the QueryResponse object the pinecone library generates.
        returned_documents = []
        for m in soft_query_response.matches:
            response = {
                'content': m.metadata['content'],
                'title': m.metadata['title'],
                'url': m.metadata['url'],
                'doc_type': m.metadata['doc_type'],
                'score': m.score,
                'id': m.id
            }
            returned_documents.append(response)
        for m in hard_query_response.matches:
            response = {
                'content': m.metadata['content'],
                'title': m.metadata['title'],
                'url': m.metadata['url'],
                'doc_type': m.metadata['doc_type'],
                'score': m.score,
                'id': m.id
            }
            returned_documents.append(response)

        return returned_documents

    def doc_relevancy_check(self, query, documents):

        with open(os.path.join('app/prompt_templates/', 'ceq_doc_check.yaml'), 'r', encoding="utf-8") as stream:
            # Load the YAML data and print the result
            prompt_template = yaml.safe_load(stream)

        doc_counter = 1
        content_strs = []
        for doc in documents:
            content_strs.append(f"{doc['title']} doc_number: [{doc_counter}]")
            documents_str = " ".join(content_strs)
            doc_counter += 1
        prompt_message  = "Query: " + query + " Documents: " + documents_str

        logit_bias_weight = 100
        # 0-9
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(documents) + 1)}
        # \n
        logit_bias["198"] = logit_bias_weight

        # Loop over the list of dictionaries in data['prompt_template']
        for role in prompt_template:
            if role['role'] == 'user':  # If the 'role' is 'user'
                role['content'] = prompt_message  # Replace the 'content' with 'prompt_message'

        response = openai.ChatCompletion.create(
            model=self.shelby_agent.config.ceq_doc_relevancy_check_llm_model,
            messages=prompt_template,
            max_tokens=10,
            logit_bias=logit_bias
        )

        doc_check = self.shelby_agent.check_response(response)
        if not doc_check:
            return None

        # This finds all instances of n in the LLM response
        pattern_num = r"\d"
        matches = re.findall(pattern_num, doc_check)

        if (len(matches) == 1 and matches[0] == '0') or len(matches) == 0:
            self.shelby_agent.log.print_and_log(f'Error in doc_check: {response}')
            return None

        relevant_documents = []
        # Creates a list of each unique mention of n in LLM response
        unique_doc_nums = set([int(match) for match in matches])
        for doc_num in unique_doc_nums:
            # doc_num given to llm has an index starting a 1
            # Subtract 1 to get the correct index in the list
            # Access the document from the list using the index
            relevant_documents.append(documents[doc_num - 1])

        return relevant_documents

    def ceq_parse_documents(self, returned_documents):

        def _tiktoken_len(document):
            tokenizer = tiktoken.encoding_for_model(self.shelby_agent.config.ceq_tiktoken_encoding_model)
            tokens = tokenizer.encode(
                document,
                disallowed_special=()
            )
            return len(tokens)

        def _docs_tiktoken_len(documents):
            tokenizer = tiktoken.encoding_for_model(self.shelby_agent.config.ceq_tiktoken_encoding_model)
            token_count = 0
            for document in documents:
                tokens = 0
                tokens += len(tokenizer.encode(
                    document['content'],
                    disallowed_special=()
                ))
                token_count += tokens
            return token_count

        # Count the number of 'hard' and 'soft' documents
        hard_count = sum(1 for doc in returned_documents if doc['doc_type'] == 'hard')
        soft_count = sum(1 for doc in returned_documents if doc['doc_type'] == 'soft')

        # Sort the list by score
        sorted_documents = sorted(returned_documents, key=lambda x: x['score'], reverse=True)

        for i, document in enumerate(sorted_documents, start=1):
            token_count = _tiktoken_len(document['content'])
            if token_count > self.shelby_agent.config.ceq_docs_max_total_tokens:
                sorted_documents.pop(idx)
                continue
            document['token_count'] = token_count
            document['doc_num'] = i

        embeddings_tokens = _docs_tiktoken_len(sorted_documents)

        self.shelby_agent.log.print_and_log(f"context docs token count: {embeddings_tokens}")
        iterations = 0
        original_documents_count = len(sorted_documents)
        while embeddings_tokens > self.shelby_agent.config.ceq_docs_max_total_tokens:
            if iterations >= original_documents_count:
                break
            # Find the index of the document with the highest token_count that exceeds ceq_docs_max_token_length
            max_token_count_idx = max((idx for idx, document in enumerate(sorted_documents) if document['token_count'] > self.shelby_agent.config.ceq_docs_max_token_length),
                    key=lambda idx: sorted_documents[idx]['token_count'], default=None)
            # If a document was found that meets the conditions, remove it from the list
            if max_token_count_idx is not None:
                doc_type = sorted_documents[max_token_count_idx]['doc_type']
                if doc_type == 'soft':
                    soft_count -= 1
                else:
                    hard_count -= 1
                sorted_documents.pop(max_token_count_idx)
                break
            # Remove the lowest scoring 'soft' document if there is more than one,
            elif soft_count > 1:
                for idx, document in reversed(list(enumerate(sorted_documents))):
                    if document['doc_type'] == 'soft':
                        sorted_documents.pop(idx)
                        soft_count -= 1
                        break
            # otherwise remove the lowest scoring 'hard' document
            elif hard_count > 1:
                for idx, document in reversed(list(enumerate(sorted_documents))):
                    if document['doc_type'] == 'hard':
                        sorted_documents.pop(idx)
                        hard_count -= 1
                        break
            else:
                # Find the index of the document with the highest token_count
                max_token_count_idx = max(range(len(sorted_documents)), key=lambda idx: sorted_documents[idx]['token_count'])
                # Remove the document with the highest token_count from the list
                sorted_documents.pop(max_token_count_idx)

            embeddings_tokens = _docs_tiktoken_len(sorted_documents)
            self.shelby_agent.log.print_and_log("removed lowest scoring embedding doc .")
            self.shelby_agent.log.print_and_log(f"context docs token count: {embeddings_tokens}")
            iterations += 1
        self.shelby_agent.log.print_and_log(f"number of context docs now: {len(sorted_documents)}")
        # Same as above but removes based on total count of docs instead of token count.
        while len(sorted_documents) > self.shelby_agent.config.ceq_docs_max_used:
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
            # sself.shelby_agent.log.print_and_log("removed lowest scoring embedding doc.")

        for i, document in enumerate(sorted_documents, start=1):
            document['doc_num'] = i

        return sorted_documents

    def ceq_main_prompt_template(self, query, documents):

        with open(os.path.join('app/prompt_templates/', 'ceq_main_prompt.yaml'), 'r', encoding="utf-8") as stream:
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

        # self.shelby_agent.log.print_and_log(f"prepared prompt: {json.dumps(prompt_template, indent=4)}")

        return prompt_template

    def ceq_main_prompt_llm(self, prompt):

        response = openai.ChatCompletion.create(
            api_key=self.shelby_agent.openai_api_key,
            model=self.shelby_agent.config.ceq_main_prompt_llm_model,
            messages=prompt,
            max_tokens=self.shelby_agent.config.ceq_max_response_tokens
        )
        prompt_response = self.shelby_agent.check_response(response)
        if not prompt_response:
            return None

        return prompt_response

    def ceq_append_meta(self, input_text, parsed_documents):

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
            self.shelby_agent.log.print_and_log("No supporting docs.")
            answer_obj = {
                "answer_text": input_text,
                "llm": self.shelby_agent.config.ceq_main_prompt_llm_model,
                "documents": []
            }
            return answer_obj
        print(matches)

        # Formatted text has all mutations of documents n replaced with [n]
        answer_obj = {
                "answer_text": formatted_text,
                "llm": self.shelby_agent.config.ceq_main_prompt_llm_model,
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
                    pass
                    self.shelby_agent.log.print_and_log(f"Document{doc_num} not found in the list.")

        self.shelby_agent.log.print_and_log(f"response with metadata: {answer_obj}")

        return answer_obj

    def run_context_enriched_query(self, query):

        data_domain_name = None
        if self.shelby_agent.config.ceq_data_domain_constraints_enabled:
            data_domain_name, response = self.select_data_domain(query)
            if response is not None:
                return response
        
        self.shelby_agent.log.print_and_log(f'Running query: {query}')

        if self.shelby_agent.config.ceq_keyword_generator_enabled:
            generated_keywords = self.keyword_generator(query)
            self.shelby_agent.log.print_and_log(f"ceq_keyword_generator response: {generated_keywords}")

        dense_embedding, sparse_embedding = self.get_query_embeddings(query)
        self.shelby_agent.log.print_and_log("Sparse and dense embeddings retrieved")

        returned_documents = self.query_vectorstore(dense_embedding, sparse_embedding, data_domain_name)
        if not returned_documents:
            pass
            self.shelby_agent.log.print_and_log("No supporting documents found!")
        returned_documents_list = []
        for returned_doc in returned_documents:
            returned_documents_list.append(returned_doc['url'])
        self.shelby_agent.log.print_and_log(f"{len(returned_documents)} documents returned from vectorstore: {returned_documents_list}")
        
        if self.shelby_agent.config.ceq_doc_relevancy_check_enabled:
            returned_documents = self.doc_relevancy_check(query, returned_documents)
            if not returned_documents:
                pass
                self.shelby_agent.log.print_and_log("No supporting documents after doc_check!")
            returned_documents_list = []
            for returned_doc in returned_documents:
                returned_documents_list.append(returned_doc['url'])
            self.shelby_agent.log.print_and_log(f"{len(returned_documents)} documents returned from doc_check: {returned_documents_list}")

        parsed_documents = self.ceq_parse_documents(returned_documents)
        final_documents_list = []
        for parsed_document in parsed_documents:
            final_documents_list.append(parsed_document['url'])
        self.shelby_agent.log.print_and_log(f"{len(parsed_documents)} documents returned after parsing: {final_documents_list}")

        prompt = self.ceq_main_prompt_template(query, parsed_documents)

        self.shelby_agent.log.print_and_log(f'Sending prompt to LLM')
        llm_response = self.ceq_main_prompt_llm(prompt)
        # self.shelby_agent.log.print_and_log(f'LLM response: {llm_response}')

        parsed_response = self.ceq_append_meta(llm_response, parsed_documents)
        self.shelby_agent.log.print_and_log(f"LLM response with appended metadata: {json.dumps(parsed_response, indent=4)}")
                    
        return parsed_response

# class APIAgent:

#     ### APIAgent makes API calls on behalf the user ###
#     # Currently under development

#     def __init__(self, shelby_agent, log_service, config):

#         self.shelby_agent = shelby_agent
#         # self.log = log_service
#         self.config = config

#     # Selects the correct API and endpoint to run action on.
#     # Eventually, we should create a merged file that describes all available API.
#     def select_API_operationID(self, query):

#         API_spec_path = self.API_spec_path
#         # Load prompt template to be used with all APIs
#         with open(os.path.join('app/prompt_templates/', 'action_topic_constraint.yaml'), 'r', encoding="utf-8") as stream:
#             # Load the YAML data and print the result
#             prompt_template = yaml.safe_load(stream)
#         operationID_file = None
#         # Iterates all OpenAPI specs in API_spec_path directory,
#         # and asks LLM if the API can satsify the request and if so which document to return
#         for entry in os.scandir(API_spec_path):
#             if entry.is_dir():
#                 # Create prompt
#                 with open(os.path.join(entry.path, 'LLM_OAS_keypoint_guide_file.txt'), 'r', encoding="utf-8") as stream:
#                     keypoint = yaml.safe_load(stream)
#                     prompt_message  = "query: " + query + " spec: " + keypoint
#                     for role in prompt_template:
#                         if role['role'] == 'user':
#                             role['content'] = prompt_message

#                     logit_bias_weight = 100
#                     # 0-9
#                     logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + 5 + 1)}
#                     # \n
#                     logit_bias["198"] = logit_bias_weight
#                     # x
#                     logit_bias["87"] = logit_bias_weight

#                     # Creates a dic of tokens that are the only acceptable answers
#                     # This forces GPT to choose one.

#                     response = openai.ChatCompletion.create(
#                         model=self.select_operationID_llm_model,
#                         messages=prompt_template,
#                         # 5 tokens when doc_number == 999
#                         max_tokens=5,
#                         logit_bias=logit_bias,
#                         stop='x'
#                     )
#             operation_response = self.shelby_agent.check_response(response)
#             if not operation_response:
#                 return None

#             # need to check if there are no numbers in answer
#             if 'x' in operation_response or operation_response == '':
#                 # Continue until you find a good operationID.
#                 continue
#             else:
#                 digits = operation_response.split('\n')
#                 number_str = ''.join(digits)
#                 number = int(number_str)
#                 directory_path = f"data/minified_openAPI_specs/{entry.name}/operationIDs/"
#                 for filename in os.listdir(directory_path):
#                     if filename.endswith(f"-{number}.json"):
#                         with open(os.path.join(directory_path, filename), 'r', encoding="utf-8") as f:
#                             operationID_file = json.load(f)
                        # self.log.print_and_log(f"operationID_file found: {os.path.join(directory_path, filename)}.")
#                         break
#                 break
#         if operationID_file is None:
            # self.log.print_and_log("No matching operationID found.")

#         return operationID_file

#     def create_bodyless_function(self, query, operationID_file):

#         with open(os.path.join('app/prompt_templates/', 'action_topic_constraint.yaml'), 'r', encoding="utf-8") as stream:
#             # Load the YAML data and print the result
#             prompt_template = yaml.safe_load(stream)

#         prompt_message  = "user_request: " + query
#         prompt_message  += f"\nurl: " + operationID_file['metadata']['server_url'] + " operationid: " + operationID_file['metadata']['operation_id']
#         prompt_message  += f"\nspec: " + operationID_file['context']
#         for role in prompt_template:
#             if role['role'] == 'user':
#                 role['content'] = prompt_message

#         response = openai.ChatCompletion.create(
#                         model=self.create_function_llm_model,
#                         messages=prompt_template,
#                         max_tokens=500,
#                     )
#         url_response = self.shelby_agent.check_response(response)
#         if not url_response:
#             return None

#         return url_response

#     def run_API_agent(self, query):

        # self.log.print_and_log(f"new action: {query}")
#         operationID_file = self.select_API_operationID(query)
#         # Here we need to run a doc_agent query if operationID_file is None
#         function = self.create_bodyless_function(query, operationID_file)
#         # Here we need to run a doc_agent query if url_maybe does not parse as a url

#         # Here we need to run a doc_agent query if the function doesn't run correctly

#         # Here we send the request to GPT to evaluate the answer

#         return response


