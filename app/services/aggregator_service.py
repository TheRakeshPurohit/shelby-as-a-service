# region Imports
import os
import sys
from datetime import datetime, timedelta
from dateutil.tz import tzutc
import yaml
import re
import random
from importlib import import_module
import openai
from dotenv import load_dotenv

from services.tiny_jmap_library.tiny_jmap_library import TinyJMAPClient
from services.data_processing_service import TextProcessing
from services.log_service import Logger
from bs4 import BeautifulSoup
from langchain.embeddings import OpenAIEmbeddings
import pinecone
from services.pinecone_io_pinecone_text.sparse import BM25Encoder
# endregion


class Aggregator:
    def __init__(self, service_name):
        self.service_name = service_name
        self.log = Logger(self.service_name, f"{self.service_name}_aggregator_service", f"{self.service_name}_aggregator_service.md", level="INFO")

        load_dotenv()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.today = datetime.now().strftime('%Y_%m_%d')
        self.moniker_dir = f'app/content_aggregator/{self.service_name}'
        self.prompt_path = 'app/prompt_templates/aggregator/'
        config_module_path = f"content_aggregator.{service_name}.config"
        self.config = import_module(config_module_path).MonikerAggregatorConfig
        

        
        # merged_stories = self.merge_stories(summarized_stories)
        # summarized_merged_stories = self.summarize_merged_stories(merged_stories)
        
        # # top_stories = self.get_top_stories(summarized_stories)
        # intro = self.create_intro(summarized_merged_stories)
        
        # hash_tags = self.create_hash_tags(summarized_merged_stories)
        
        # post = self.create_post(summarized_merged_stories, intro, hash_tags)
        
        # self.archive_emails(relevant_emails)

        self.log.print_and_log(f"Total cost: ${self.calculate_cost()}")
        
    def check_response(self, response):
        # Check if keys exist in dictionary
        parsed_response = (
            response.get("choices", [{}])[0].get("message", {}).get("content")       
        )
        
        self.total_prompt_tokens += int(response.get("usage").get("prompt_tokens", 0))
        self.total_completion_tokens += int(response.get("usage").get("completion_tokens", 0))
        
        if not parsed_response:
            raise ValueError(f'Error in response: {response}')

        return parsed_response
    
    def calculate_cost(self):
        prompt_cost = 0.03 * (self.total_prompt_tokens / 1000)
        completion_cost = 0.06 * (self.total_completion_tokens / 1000)
        total_cost = prompt_cost + completion_cost
        # total_cost = math.ceil(total_cost * 100) / 100
        return total_cost

    def aggregate(self):
        self.email_ag = AggregateEmailNewsletter(self)
        stories = self.email_ag.aggregate_email_newsletters()
        self.vector_db = UpsertToIndex(self)
        self.vector_db.upsert(stories)
        
class AggregateEmailNewsletter:
    def __init__(self, main_ag: Aggregator):
        self.main_ag = main_ag
        self.run_output_dir = self.create_folder()
        
    def aggregate_email_newsletters(self):
        incoming_emails = self.get_emails()
        relevant_emails = self.pre_check_email(incoming_emails)
        stories = self.split_summarize(relevant_emails)
        self.archive_emails(relevant_emails)
        return stories
        
    def create_folder(self):
        aggregations_path = f'{self.main_ag.moniker_dir}/aggregations'
        # Initialize run number
        run_num = 1
        
        # Construct initial directory path
        run_output_dir = os.path.join(aggregations_path, f"{self.main_ag.today}_run_{run_num}")

        # While a directory with the current run number exists, increment the run number
        while os.path.exists(run_output_dir):
            run_num += 1
            run_output_dir = os.path.join(aggregations_path, f"{self.main_ag.today}_run_{run_num}")

        # Create the directory
        os.makedirs(run_output_dir, exist_ok=True)
        
        return run_output_dir

    def get_emails(self):
        
        # Get the current UTC date and time
        now = datetime.now(tzutc())
        start_time = now - timedelta(hours=self.main_ag.config.email_time_range)
        # This date format required
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        client = TinyJMAPClient(
            hostname="api.fastmail.com",
            username=os.environ.get("JMAP_USERNAME"),
            token=os.environ.get("JMAP_TOKEN")
        )
        account_id = client.get_account_id()

        # Query for the mailbox ID
        inbox_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Mailbox/query",
                        {
                            "accountId": account_id,
                            "filter": {"name": self.main_ag.config.newsletter_inbox},
                        },
                        "a",
                    ]
                ],
            }
        )
  
        inbox_id = inbox_res["methodResponses"][0][1]["ids"][0]
        assert len(inbox_id) > 0
        
        email_query_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Email/query",
                        {
                            "accountId": account_id,
                            "filter": {
                                "inMailbox": inbox_id,
                                'after': start_time_str,
                                'before': now_str,
                            },
                            'limit': 50,
                        },
                        "b",
                    ]
                ],
            }
        )
        
        # Extract the email IDs from the response
        email_ids = email_query_res['methodResponses'][0][1]['ids']

        # Get the email objects
        email_get_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Email/get",
                        {
                            "accountId": account_id,
                            "ids": email_ids,
                            "properties": [ 
                                "id", "blobId", "threadId", "mailboxIds", "keywords", "size",
                                "receivedAt", "messageId", "inReplyTo", "references", "sender", "from",
                                "to", "cc", "bcc", "replyTo", "subject", "sentAt", "hasAttachment",
                                "preview", "bodyValues", "textBody", "htmlBody" 
                            ],
                            "bodyProperties": ["partId", "blobId", "size", "name", "type", "charset", "disposition", "cid", "language", "location"],
                            "fetchAllBodyValues": True,
                            "fetchHTMLBodyValues": True,
                            "fetchTextBodyValues": True,
                        },
                        "c",
                    ]
                ],
            }
        )
        
        emails = email_get_res["methodResponses"][0][1]["list"]
        sorted_emails = sorted(emails, key=lambda email: email['receivedAt'])
        incoming_emails = []
        email_count = 0
        for email in sorted_emails:
            if 'htmlBody' in email and email['htmlBody']:
                body_part_id = email["htmlBody"][0]["partId"]
            elif 'textBody' in email and email['textBody']:
                body_part_id = email["textBody"][0]["partId"]
            else:
                continue  # Skip this email if neither htmlBody nor textBody is present
            body_content = email["bodyValues"][body_part_id]["value"]
            
            email_info = {
                'email_id': email['id'],
                'subject': email['subject'],
                'incoming_email_number': email_count,
                'from': email['from'][0]['email'],
                'received_at': email['receivedAt'],
                'text': body_content,
                'links': [''],  # Placeholder for future implementation
            }
            incoming_emails.append(email_info)
            email_count += 1

        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/1_incoming_emails.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(incoming_emails, yaml_file, default_flow_style=False)
        
        return incoming_emails
    
    def pre_check_email(self, incoming_emails=None):
        
        if not incoming_emails:
            self.main_ag.log.print_and_log('No emails in inbox.')
            sys.exit()
        
        with open(os.path.join(self.main_ag.prompt_path, 'aggregator_pre_check_email_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
            
        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + 2)}
        relevant_emails = []
        email_count = 0
        
        for email in incoming_emails:
            if email_count >= self.main_ag.config.email_max_per_run:
                continue
            soup = BeautifulSoup(email['text'], 'html.parser')
            bs4_text_content = soup.get_text()
            # Removes excessive whitespace chars
            text_content = TextProcessing.strip_excess_whitespace(bs4_text_content)
            # Removes start/end of the string
            chars_to_remove = min(len(text_content), self.main_ag.config.email_footer_removed_chars)
            text_content = text_content[:-chars_to_remove]
            chars_to_remove = min(len(text_content), self.main_ag.config.email_footer_removed_chars)
            text_content = text_content[chars_to_remove:]
            
            tok = TextProcessing.tiktoken_len(text_content)
            
            self.main_ag.log.print_and_log(f"email token count: {tok}")
            
            match tok:
                case _ if tok > self.main_ag.config.email_token_count_max:
                    self.main_ag.log.print_and_log(f"{email['subject']}\n exceded email_token_count_max!")
                    self.archive_emails([email])
                    continue
                case _ if tok > 2500:
                    email_pre_check_window = 0.48
                case _ if tok > 2000:
                    email_pre_check_window = 0.45
                case _ if tok > 1500:
                    email_pre_check_window = 0.40
                case _ if tok > 1000:
                    email_pre_check_window = 0.35
                case _ if tok > 500:
                    email_pre_check_window = 0.30
                case _ if tok < 500:
                    email_pre_check_window = 0.25
                case _ if tok < 200: 
                    self.main_ag.log.print_and_log(f"{email['subject']}\ntoo short!")
                    self.archive_emails([email])
                    continue
            
            length = len(text_content)
            start_index = int(length * email_pre_check_window)
            end_index = int(length * (1 - email_pre_check_window))

            prompt_template[1]['content'] = text_content[start_index:end_index]

            response = openai.ChatCompletion.create(
                api_key=os.environ.get('OPENAI_API_KEY'),
                model=self.main_ag.config.LLM_decision_model,
                messages=prompt_template,
                max_tokens=1,
                logit_bias=logit_bias
            )

            checked_response = self.main_ag.check_response(response)
            if checked_response == '0':
                self.main_ag.log.print_and_log(f"{email['subject']}\n LLM thinks it's not ad. Keeping it!")

                email['text'] = text_content
                email['relevant_email_number'] = email_count
                
                relevant_emails.append(email)
                email_count += 1
            else:
                self.main_ag.log.print_and_log(f"{email['subject']}\n LLM thinks it's an ad. Rejected!")
                self.archive_emails([email])
                
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/2_relevant_emails.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(relevant_emails, yaml_file, default_flow_style=False)

        return relevant_emails
    
    def split_summarize(self, relevant_emails):
        with open(os.path.join(self.main_ag.prompt_path, 'aggregator_split_summarize_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
        
        pre_split_output = []
        stories = []
        stories_count = 0

        
        for email in relevant_emails:
            
            content = f"{email['text']}"
            self.main_ag.log.print_and_log(f"\nNow splitting and summarizing: {email['subject']}")
            
            # Loop over the list of dictionaries in data['prompt_template']
            for role in prompt_template:
                if role['role'] == 'user':  # If the 'role' is 'user'
                    role['content'] = content  # Replace the 'content' with 'prompt_message'

            response = openai.ChatCompletion.create(
                api_key=os.environ.get('OPENAI_API_KEY'),
                model=self.main_ag.config.LLM_writing_model,
                messages=prompt_template,
                max_tokens=750,
            )

            checked_response = self.main_ag.check_response(response)
            
            self.log.print_and_log(f'split_summarize response token count: {TextProcessing.tiktoken_len(checked_response)}')
            
            email['summary'] = checked_response
            pre_split_output.append(email)
            
            # Detect if LLM returned a numbered list or [n] notation and split with appropriate pattern
            # Split the text by patterns of numbered lists like n.
            list_pattern = r"\s+\d\.(?!\d)\s+"
            list_matches = re.findall(list_pattern, checked_response)
            # Split the text by patterns of [n], (n)
            brackets_pattern = r"\[\d+\]|\(\d+\)"
            brackets_matches = re.findall(brackets_pattern, checked_response)
            if len(list_matches) > len(brackets_matches):
                # Removes the first item in the linked list if it starts with "n. "
                checked_response = re.sub(r'^\d\.\s', '', checked_response)
                splits = re.split(list_pattern, checked_response)
            else: 
                splits = re.split(brackets_pattern, checked_response)
                
            
            # self.log.print_and_log each part
            for story in splits:
                
                story = TextProcessing.remove_all_white_space_except_space(story)
                story_token_count = TextProcessing.tiktoken_len(story)
                
                if  story_token_count > self.main_ag.config.story_token_count_min:
                    story_info = {
                        'title': email['subject'],
                        'story_number': stories_count,
                        'data_source_name': email['from'],
                        'date_indexed': email['received_at'],
                        'content': story,
                        'links': [''],  # Placeholder for future implementation
                        'url': '', # Placeholder for future implementation of browser available newsletters
                        'target_type': 'email_text'
                    }
        
                    stories.append(story_info)
                    stories_count += 1
                
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/3_all_stories.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(stories, yaml_file, default_flow_style=False)
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/3b_pre_split_output.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(pre_split_output, yaml_file, default_flow_style=False)

        return stories
    
    def archive_emails(self, incoming_emails):
        
        client = TinyJMAPClient(
            hostname="api.fastmail.com",
            username=os.environ.get("JMAP_USERNAME"),
            token=os.environ.get("JMAP_TOKEN")
        )
        account_id = client.get_account_id()

        # Query for the mailbox ID
        inbox_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Mailbox/query",
                        {
                            "accountId": account_id,
                            "filter": {"name": self.main_ag.config.email_ingested_folder},
                        },
                        "a",
                    ]
                ],
            }
        )
        inbox_id = inbox_res["methodResponses"][0][1]["ids"][0]
        assert len(inbox_id) > 0
        
        email_ids = [email['email_id'] for email in incoming_emails]
        updates = {email_id: {"mailboxIds": {inbox_id: True}} for email_id in email_ids}
        email_query_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Email/set",
                        {
                            "accountId": account_id,
                            "update": updates
                        },
                        "0"
                    ]
                ]
            }
        )
        response_data = email_query_res['methodResponses'][0][1]

        for email_id in email_ids:
            if 'updated' in response_data and email_id in response_data['updated']:
                self.log.print_and_log(f"Email with ID {email_id} moved to {self.main_ag.config.email_ingested_folder}!")
            elif 'notUpdated' in response_data and email_id in response_data['notUpdated']:
                error = response_data['notUpdated'][email_id]['type']
                self.log.print_and_log(f"Email with ID {email_id} update failed with error: {error}")
            else:
                self.log.print_and_log(f"Unexpected response for email with ID {email_id}!")

class UpsertToIndex:
    def __init__(self, main_ag: Aggregator):
        self.main_ag = main_ag
        pinecone.init(
            environment=self.main_ag.index_env,
            api_key=os.environ.get('PINECONE_API_KEY'), 
        )

        indexes = pinecone.list_indexes()
        if self.main_ag.index_name not in indexes:
            self.main_ag.log.print_and_log(f"{self.main_ag.index_name} not found in Pinecone")
            
        self.vectorstore = pinecone.Index(self.main_ag.index_name)

    def upsert_text(self, content):
        
        self.main_ag.log.print_and_log(f'Initial index stats: {self.vectorstore.describe_index_stats()}\n')
        self.main_ag.log.print_and_log(f'-----Now indexing: {len(content)} text stories\n')
        index_resource_stats = self.vectorstore.describe_index_stats(
            filter={
                'target_type': {"$eq": 'email_text'}
                }
            )
        existing_resource_vector_count = index_resource_stats.get('namespaces', {}).get(self.main_ag.index_namespace, {}).get('vector_count', 0)
        self.main_ag.log.print_and_log(f"Existing vector count for {self.main_ag.index_namespace}: {existing_resource_vector_count}")

        embedding_retriever = OpenAIEmbeddings(
            model=self.config.index_embedding_model,
            embedding_ctx_length=self.config.index_embedding_max_chunk_size,
            openai_api_key=self.index_agent.secrets['openai_api_key'],
            chunk_size=self.config.index_embedding_batch_size,
            request_timeout=self.config.index_openai_timeout_seconds
        )

        bm25_encoder = BM25Encoder()
        
        
        
        # Get dense_embeddings
        dense_embeddings = embedding_retriever.embed_documents(text_chunks)

        # Get sparse_embeddings
        # Pretrain "corpus"
        bm25_encoder.fit(text_chunks)
        sparse_embeddings = bm25_encoder.encode_documents(text_chunks)
        self.main_ag.log.print_and_log(f'Embeddings created. Dense: {len(dense_embeddings)} Sparse: {len(sparse_embeddings)}')
        

        # If the "resource" already has vectors delete the existing vectors before upserting new vectors
        # We have to delete all because the difficulty in specifying specific documents in pinecone
        if existing_resource_vector_count != 0:
            self.clear_data_source(data_source)
            index_resource_stats = self.vectorstore.describe_index_stats(
            filter={
                'data_source_name': {"$eq": data_source.data_source_name}
                }
            )
            cleared_resource_vector_count = index_resource_stats.get('namespaces', {}).get(self.deployment_name, {}).get('vector_count', 0)
            self.main_ag.log.print_and_log(f'Removing pre-existing vectors. New count: {cleared_resource_vector_count} (should be 0)')
        
        
        vectors_to_upsert = []
        vector_counter = 0
        for i, document_chunk in enumerate(document_chunks):
            prepared_vector = {
                "id": f"id-{data_source.data_source_name}-{vector_counter}",
                "values": dense_embeddings[i],  
                "metadata": document_chunk,  
                'sparse_values': sparse_embeddings[i]
            }
            vector_counter += 1
            vectors_to_upsert.append(prepared_vector)

        self.main_ag.log.print_and_log(f'Upserting {len(vectors_to_upsert)} vectors')
        self.vectorstore.upsert(
            vectors=vectors_to_upsert,               
            namespace=self.deployment_name,
            batch_size=self.config.index_vectorstore_upsert_batch_size,
            show_progress=True                 
        )
        
        index_resource_stats = self.vectorstore.describe_index_stats(
        filter={
            'data_source_name': {"$eq": data_source.data_source_name}
            }
        )
        new_resource_vector_count = index_resource_stats.get('namespaces', {}).get(self.deployment_name, {}).get('vector_count', 0)
        self.main_ag.log.print_and_log(f'Indexing complete for: {data_source.data_source_name}\nPrevious vector count: {existing_resource_vector_count}\nNew vector count: {new_resource_vector_count}\n')
        # self.main_ag.log.print_and_log(f'Post-upsert index stats: {index_resource_stats}\n')
        
        data_source.preprocessor.write_chunks(data_source, document_chunks)
        
        # If completed successfully, break the retry loop
        break


    self.main_ag.log.print_and_log(f'Final index stats: {self.vectorstore.describe_index_stats()}')
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
        
class oldClass:
    def __init__(self, service_name):
        load_dotenv()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        
        self.service_name = service_name
        self.today = datetime.now().strftime('%Y_%m_%d')
        self.moniker_dir = f'app/content_aggregator/{self.service_name}'
        self.prompt_path = 'app/prompt_templates/aggregator/'
        config_module_path = f"content_aggregator.{service_name}.config"
        self.config = import_module(config_module_path).MonikerAggregatorConfig
        
        self.run_output_dir = self.create_folder()
        incoming_emails = self.get_emails()
        relevant_emails = self.pre_check_email(incoming_emails)
        
        summarized_stories = self.split_summarize(relevant_emails)
        summarized_stories = self.create_titles(summarized_stories)
        summarized_stories = self.create_emojis(summarized_stories)
        
        merged_stories = self.merge_stories(summarized_stories)
        summarized_merged_stories = self.summarize_merged_stories(merged_stories)
        
        # top_stories = self.get_top_stories(summarized_stories)
        intro = self.create_intro(summarized_merged_stories)
        
        hash_tags = self.create_hash_tags(summarized_merged_stories)
        
        post = self.create_post(summarized_merged_stories, intro, hash_tags)
        
        self.archive_emails(relevant_emails)

        self.log.print_and_log(f"Total cost: ${self.calculate_cost()}")
        
    def create_folder(self):
        aggregations_path = f'{self.moniker_dir}/aggregations'
        # Initialize run number
        run_num = 1
        
        # Construct initial directory path
        run_output_dir = os.path.join(aggregations_path, f"{self.today}_run_{run_num}")

        # While a directory with the current run number exists, increment the run number
        while os.path.exists(run_output_dir):
            run_num += 1
            run_output_dir = os.path.join(aggregations_path, f"{self.today}_run_{run_num}")

        # Create the directory
        os.makedirs(run_output_dir, exist_ok=True)
        
        return run_output_dir

    def get_emails(self):
        
        # Get the current UTC date and time
        now = datetime.now(tzutc())
        start_time = now - timedelta(hours=self.config.email_time_range)
        # This date format required
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        client = TinyJMAPClient(
            hostname="api.fastmail.com",
            username=os.environ.get("JMAP_USERNAME"),
            token=os.environ.get("JMAP_TOKEN")
        )
        account_id = client.get_account_id()

        # Query for the mailbox ID
        inbox_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Mailbox/query",
                        {
                            "accountId": account_id,
                            "filter": {"name": self.config.newsletter_inbox},
                        },
                        "a",
                    ]
                ],
            }
        )
  
        inbox_id = inbox_res["methodResponses"][0][1]["ids"][0]
        assert len(inbox_id) > 0
        
        email_query_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Email/query",
                        {
                            "accountId": account_id,
                            "filter": {
                                "inMailbox": inbox_id,
                                'after': start_time_str,
                                'before': now_str,
                            },
                            'limit': 50,
                        },
                        "b",
                    ]
                ],
            }
        )
        
        # Extract the email IDs from the response
        email_ids = email_query_res['methodResponses'][0][1]['ids']

        # Get the email objects
        email_get_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Email/get",
                        {
                            "accountId": account_id,
                            "ids": email_ids,
                            "properties": [ 
                                "id", "blobId", "threadId", "mailboxIds", "keywords", "size",
                                "receivedAt", "messageId", "inReplyTo", "references", "sender", "from",
                                "to", "cc", "bcc", "replyTo", "subject", "sentAt", "hasAttachment",
                                "preview", "bodyValues", "textBody", "htmlBody" 
                            ],
                            "bodyProperties": ["partId", "blobId", "size", "name", "type", "charset", "disposition", "cid", "language", "location"],
                            "fetchAllBodyValues": True,
                            "fetchHTMLBodyValues": True,
                            "fetchTextBodyValues": True,
                        },
                        "c",
                    ]
                ],
            }
        )
        
        emails = email_get_res["methodResponses"][0][1]["list"]
        sorted_emails = sorted(emails, key=lambda email: email['receivedAt'])
        incoming_emails = []
        email_count = 0
        for email in sorted_emails:
            if 'htmlBody' in email and email['htmlBody']:
                body_part_id = email["htmlBody"][0]["partId"]
            elif 'textBody' in email and email['textBody']:
                body_part_id = email["textBody"][0]["partId"]
            else:
                continue  # Skip this email if neither htmlBody nor textBody is present
            body_content = email["bodyValues"][body_part_id]["value"]
            
            email_info = {
                'email_id': email['id'],
                'subject': email['subject'],
                'number': email_count,
                'from': email['from'][0]['email'],
                'received_at': email['receivedAt'],
                'text': body_content,
                'links': [''],  # Placeholder for future implementation
            }
            incoming_emails.append(email_info)
            email_count += 1

        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/1_incoming_emails.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(incoming_emails, yaml_file, default_flow_style=False)
        
        return incoming_emails
    
    def archive_emails(self, incoming_emails):
        
        client = TinyJMAPClient(
            hostname="api.fastmail.com",
            username=os.environ.get("JMAP_USERNAME"),
            token=os.environ.get("JMAP_TOKEN")
        )
        account_id = client.get_account_id()

        # Query for the mailbox ID
        inbox_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Mailbox/query",
                        {
                            "accountId": account_id,
                            "filter": {"name": self.config.email_ingested_folder},
                        },
                        "a",
                    ]
                ],
            }
        )
        inbox_id = inbox_res["methodResponses"][0][1]["ids"][0]
        assert len(inbox_id) > 0
        
        email_ids = [email['email_id'] for email in incoming_emails]
        updates = {email_id: {"mailboxIds": {inbox_id: True}} for email_id in email_ids}
        email_query_res = client.make_jmap_call(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    [
                        "Email/set",
                        {
                            "accountId": account_id,
                            "update": updates
                        },
                        "0"
                    ]
                ]
            }
        )
        response_data = email_query_res['methodResponses'][0][1]

        for email_id in email_ids:
            if 'updated' in response_data and email_id in response_data['updated']:
                self.log.print_and_log(f"Email with ID {email_id} moved to {self.config.email_ingested_folder}!")
            elif 'notUpdated' in response_data and email_id in response_data['notUpdated']:
                error = response_data['notUpdated'][email_id]['type']
                self.log.print_and_log(f"Email with ID {email_id} update failed with error: {error}")
            else:
                self.log.print_and_log(f"Unexpected response for email with ID {email_id}!")

    def check_response(self, response):
        # Check if keys exist in dictionary
        parsed_response = (
            response.get("choices", [{}])[0].get("message", {}).get("content")       
        )
        
        self.total_prompt_tokens += int(response.get("usage").get("prompt_tokens", 0))
        self.total_completion_tokens += int(response.get("usage").get("completion_tokens", 0))
        
        if not parsed_response:
            raise ValueError(f'Error in response: {response}')

        return parsed_response
    
    def calculate_cost(self):
        prompt_cost = 0.03 * (self.total_prompt_tokens / 1000)
        completion_cost = 0.06 * (self.total_completion_tokens / 1000)
        total_cost = prompt_cost + completion_cost
        # total_cost = math.ceil(total_cost * 100) / 100
        return total_cost
        
    def pre_check_email(self, incoming_emails=None):
        if not incoming_emails:
            self.log.print_and_log('No emails in inbox.')
            sys.exit()
        
        with open(os.path.join(self.prompt_path, 'aggregator_pre_check_email_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
            
        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + 2)}
        relevant_emails = []
        email_count = 0
        
        for email in incoming_emails:
            if email_count >= self.config.email_max_per_run:
                continue
            soup = BeautifulSoup(email['text'], 'html.parser')
            bs4_text_content = soup.get_text()
            # Removes excessive whitespace chars
            text_content = TextProcessing.strip_excess_whitespace(bs4_text_content)
            # Removes start/end of the string
            chars_to_remove = min(len(text_content), self.config.email_footer_removed_chars)
            text_content = text_content[:-chars_to_remove]
            chars_to_remove = min(len(text_content), self.config.email_footer_removed_chars)
            text_content = text_content[chars_to_remove:]
            
            tok = TextProcessing.tiktoken_len(text_content)
            
            self.log.print_and_log(f"email token count: {tok}")
            
            match tok:
                case _ if tok > self.config.email_token_count_max:
                    self.log.print_and_log(f"{email['subject']}\n exceded email_token_count_max!")
                    self.archive_emails([email])
                    continue
                case _ if tok > 2500:
                    email_pre_check_window = 0.48
                case _ if tok > 2000:
                    email_pre_check_window = 0.45
                case _ if tok > 1500:
                    email_pre_check_window = 0.40
                case _ if tok > 1000:
                    email_pre_check_window = 0.35
                case _ if tok > 500:
                    email_pre_check_window = 0.30
                case _ if tok < 500:
                    email_pre_check_window = 0.25
                case _ if tok < 200: 
                    self.log.print_and_log(f"{email['subject']}\ntoo short!")
                    self.archive_emails([email])
                    continue
            
            length = len(text_content)
            start_index = int(length * email_pre_check_window)
            end_index = int(length * (1 - email_pre_check_window))

            prompt_template[1]['content'] = text_content[start_index:end_index]

            response = openai.ChatCompletion.create(
                api_key=os.environ.get('OPENAI_API_KEY'),
                model=self.config.LLM_decision_model,
                messages=prompt_template,
                max_tokens=1,
                logit_bias=logit_bias
            )

            checked_response = self.check_response(response)
            if checked_response == '0':
                self.log.print_and_log(f"{email['subject']}\n LLM thinks it's not ad. Keeping it!")
                email_info = {
                    'email_id': email['email_id'],
                    'subject': email['subject'],
                    'number': email_count,
                    'from': email['from'],
                    'received_at': email['received_at'],
                    'text': text_content,
                    'links': [''],  # Placeholder for future implementation
                }
                relevant_emails.append(email_info)
                email_count += 1
            else:
                self.log.print_and_log(f"{email['subject']}\n LLM thinks it's an ad. Rejected!")
                self.archive_emails([email])
                
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/2_relevant_emails.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(relevant_emails, yaml_file, default_flow_style=False)

        return relevant_emails
    
    def split_summarize(self, relevant_emails):
        with open(os.path.join(self.prompt_path, 'aggregator_split_summarize_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
        
        pre_split_output = []
        split_summarized_stories = []
        stories_count = 0

        
        for email in relevant_emails:
            
            content = f"{email['text']}"
            self.log.print_and_log(f"\nNow splitting and summarizing: {email['subject']}")
            
            # Loop over the list of dictionaries in data['prompt_template']
            for role in prompt_template:
                if role['role'] == 'user':  # If the 'role' is 'user'
                    role['content'] = content  # Replace the 'content' with 'prompt_message'

            response = openai.ChatCompletion.create(
                api_key=os.environ.get('OPENAI_API_KEY'),
                model=self.config.LLM_writing_model,
                messages=prompt_template,
                max_tokens=750,
            )

            checked_response = self.check_response(response)
            
            self.log.print_and_log(f'split_summarize response token count: {TextProcessing.tiktoken_len(checked_response)}')
            pre_split_response = {
                'subject': email['subject'],
                'story_number': email['number'],
                'from': email['from'],
                'received_at': email['received_at'],
                'summary': checked_response,
                'links': [''],  # Placeholder for future implementation
            }
            pre_split_output.append(pre_split_response)
            # Detect if LLM returned a numbered list or [n] notation and split with appropriate pattern
            # Split the text by patterns of numbered lists like n.
            list_pattern = r"\s+\d\.(?!\d)\s+"
            list_matches = re.findall(list_pattern, checked_response)
            # Split the text by patterns of [n], (n)
            brackets_pattern = r"\[\d+\]|\(\d+\)"
            brackets_matches = re.findall(brackets_pattern, checked_response)
            if len(list_matches) > len(brackets_matches):
                # Removes the first item in the linked list if it starts with "n. "
                checked_response = re.sub(r'^\d\.\s', '', checked_response)
                splits = re.split(list_pattern, checked_response)
            else: 
                splits = re.split(brackets_pattern, checked_response)
                
            
            # self.log.print_and_log each part
            for story in splits:
                
                story = TextProcessing.remove_all_white_space_except_space(story)
                story_token_count = TextProcessing.tiktoken_len(story)
                
                if  story_token_count > self.config.story_token_count_min:
                    story_info = {
                        'subject': email['subject'],
                        'story_number': stories_count,
                        'from': email['from'],
                        'received_at': email['received_at'],
                        'summary': story,
                        'links': [''],  # Placeholder for future implementation
                    }
                    split_summarized_stories.append(story_info)
                    stories_count += 1
                
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/3_all_stories.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(split_summarized_stories, yaml_file, default_flow_style=False)
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/3b_pre_split_output.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(pre_split_output, yaml_file, default_flow_style=False)

        return split_summarized_stories
    
    def create_titles(self, list_of_stories):
        with open(os.path.join(self.prompt_path, 'aggregator_create_titles_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
        
        for story in list_of_stories:
            content = f"Story: {story['summary']}"
        
            for role in prompt_template:
                if role['role'] == 'user':  
                    role['content'] = content  

            response = openai.ChatCompletion.create(
                api_key=os.environ.get('OPENAI_API_KEY'),
                model=self.config.LLM_writing_model,
                messages=prompt_template,
                max_tokens=10,
            )
            checked_response = self.check_response(response)
            story['title'] = checked_response
        
        return list_of_stories
            
    def merge_stories(self, split_summarized_stories_titles):
        with open(os.path.join(self.prompt_path, 'aggregator_merge_stories_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
        
        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + 2)}
        
        merged_stories = []
        merged_checked_story_numbers = []
        merged_story_counter = 0
        
        for story in split_summarized_stories_titles:
            if story['story_number'] in merged_checked_story_numbers:
                continue
            
            active_story = {
                'subject': story['subject'],
                'emoji': story['emoji'],
                'title': story['title'],
                'story_number': story['story_number'],
                'merged_story_number': merged_story_counter,
                'from': story['from'],
                'received_at': story['received_at'],
                'summary': story['summary'],
                'links': [''],  # Placeholder for future implementation
                }
            
            merged_stories.append(active_story)
            merged_checked_story_numbers.append(story['story_number'])

            for comparison_story in split_summarized_stories_titles:
                if comparison_story['story_number'] in merged_checked_story_numbers:
                    continue
                
                content = f"Story 1: {story['summary']}\n Story 2: {comparison_story['summary']}"
            
                for role in prompt_template:
                    if role['role'] == 'user':  
                        role['content'] = content  

                response = openai.ChatCompletion.create(
                    api_key=os.environ.get('OPENAI_API_KEY'),
                    model=self.config.LLM_decision_model,
                    messages=prompt_template,
                    max_tokens=1,
                    logit_bias=logit_bias
                )

                checked_response = self.check_response(response)
                
                if checked_response == '1':
    
                    self.log.print_and_log(f"Active story {story['story_number']} and comparison story {comparison_story['story_number']} match!")
                    self.log.print_and_log(f"Saving as merged story number {merged_story_counter}")
                    
                    matched_info = {
                        'subject': comparison_story['subject'],
                        'title': comparison_story['title'],
                        'emoji': comparison_story['emoji'],
                        'story_number': comparison_story['story_number'],
                        'merged_story_number': merged_story_counter,
                        'from': comparison_story['from'],
                        'received_at': comparison_story['received_at'],
                        'summary': comparison_story['summary'],
                        'links': [''],  # Placeholder for future implementation
                    }

                    merged_stories.append(matched_info)
                    merged_checked_story_numbers.append(comparison_story['story_number'])
                    
            merged_story_counter += 1
            
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/4_merged_stories.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(merged_stories, yaml_file, default_flow_style=False)
            
        return merged_stories
    
    def summarize_merged_stories(self, merged_stories):       
        with open(os.path.join(self.prompt_path, 'aggregator_summarize_merged_stories_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)

        summarized_stories = []
        summarized_story_numbers = []
        
        for story in merged_stories:
            if story['story_number'] in summarized_story_numbers:
                continue
            summarized_story_numbers.append(story['story_number'])
            
            active_summary = {}
            active_summary = {
                'merged_story_number': story['merged_story_number'],
                'summary': story['summary'],
                'title': story['title'],
                'emoji': story['emoji'],
                'stories': [],
                }
            active_summary['stories'].append(story)
            
            content = f"Story: {story['summary']}\n"

            multiple_stories = False
            for comparison_story in merged_stories:
                if comparison_story['story_number'] in summarized_story_numbers:
                    continue
                if comparison_story['merged_story_number'] == story['merged_story_number']:
                    multiple_stories = True
                    summarized_story_numbers.append(comparison_story['story_number'])
                    active_summary['stories'].append(comparison_story)
                    
                    content += f"Story: {comparison_story['summary']}\n"
            
            # Skip summarization if there aren't multiple stories to merge
            if multiple_stories:
                for role in prompt_template:
                    if role['role'] == 'user':  
                        role['content'] = content  

                response = openai.ChatCompletion.create(
                    api_key=os.environ.get('OPENAI_API_KEY'),
                    model=self.config.LLM_writing_model,
                    messages=prompt_template,
                    max_tokens=100
                )
                checked_response = self.check_response(response)
                active_summary['summary'] = checked_response
                
                # Creates title from summary. 
                with open(os.path.join(self.prompt_path, 'aggregator_create_titles_template.yaml'), 'r', encoding="utf-8") as stream:
                    title_template = yaml.safe_load(stream)
        
                for role in title_template:
                    if role['role'] == 'user':  
                        role['content'] = checked_response  
                response = openai.ChatCompletion.create(
                    api_key=os.environ.get('OPENAI_API_KEY'),
                    model=self.config.LLM_writing_model,
                    messages=title_template,
                    max_tokens=8,
                )
                checked_response = self.check_response(response)
                active_summary['title'] = checked_response
                
                
            summarized_stories.append(active_summary)
     
                
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/5_summarized_stories.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(summarized_stories, yaml_file, default_flow_style=False)
            
        return summarized_stories
    
    def get_top_stories(self, summarized_stories):
        if len(summarized_stories) < self.config.post_max_stories:
            return summarized_stories
        
        multiple_items_summaries = []
        single_item_summaries = []
        # Split into two lists of stories with more than one source, and summaries with just one source
        for story_summary in summarized_stories:
            if len(story_summary['stories']) > 1:
                multiple_items_summaries.append(story_summary)
            elif len(story_summary['stories']) == 1:
                single_item_summaries.append(story_summary)
        # If we have enough multiple source stories just sort and cut off the lowest source numbered stories
        if len(multiple_items_summaries) > self.config.post_max_stories:
            sorted_multiple_items_summaries = sorted(multiple_items_summaries, key=lambda x: len(x['stories']), reverse=True)
            top_summaries = sorted_multiple_items_summaries[:self.config.post_max_stories]
            return top_summaries

        # Else we ask GPT to pick
        output_list = list(multiple_items_summaries)
        number_multi_source_stories = len(multiple_items_summaries)
        number_stories_required = self.config.post_max_stories - number_multi_source_stories
            
        with open(os.path.join(self.prompt_path, 'aggregator_get_top_stories_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)

        # Remove at random to reduce to less than 9. Need to rewrite to extend logit bias options
        while len(single_item_summaries) > 9:
            single_item_summaries.pop(random.randint(0, len(single_item_summaries) - 1))
        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(single_item_summaries))}
        
        content = ''
        counter = 0
        for summary in single_item_summaries:
            summary['top_stories_key'] = counter
            content += f"{counter}. {summary['title']}\n"
            counter += 1
            
        for role in prompt_template:
            if role['role'] == 'user':  
                role['content'] = content  

        response = openai.ChatCompletion.create(
            api_key=os.environ.get('OPENAI_API_KEY'),
            model=self.config.LLM_writing_model,
            messages=prompt_template,
            max_tokens=number_stories_required,
            logit_bias=logit_bias,
        )
        checked_response = self.check_response(response)
        digits_list = [int(char) for char in checked_response if char in '123456789']
        for number in digits_list:
            for summary in single_item_summaries:
                if int(summary['top_stories_key']) == number:
                    output_list.append(summary)
                    
        return output_list
            
    def create_intro(self, summarized_stories):

        with open(os.path.join(self.prompt_path, 'aggregator_create_intro_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
            
        content = f"Username: {self.config.moniker_name}\n"
        for summary in summarized_stories:
            content += f"Story title: {summary['title']}\n"
            
        for role in prompt_template:
                if role['role'] == 'user':  
                    role['content'] = content  

        response = openai.ChatCompletion.create(
            api_key=os.environ.get('OPENAI_API_KEY'),
            model=self.config.LLM_writing_model,
            messages=prompt_template,
            max_tokens=50
        )
        checked_response = self.check_response(response)
        
        return checked_response
    
    def create_hash_tags(self, summarized_stories):
        
        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 64 + 26)}
        # #
        logit_bias["2"] = logit_bias_weight
        # ' '
        logit_bias["220"] = logit_bias_weight
        
        with open(os.path.join(self.prompt_path, 'aggregator_create_hash_tags_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
            
        content = f"Keyowrds: {self.config.topic_keywords}"
        for summary in summarized_stories:
            content += f"Story: {summary['title']}\n"
            
        for role in prompt_template:
                if role['role'] == 'user':  
                    role['content'] = content  

        response = openai.ChatCompletion.create(
            api_key=os.environ.get('OPENAI_API_KEY'),
            model=self.config.LLM_writing_model,
            messages=prompt_template,
            max_tokens=50,
        )
        checked_response = self.check_response(response)
        
        filtered = re.sub(r'[^a-z #]', '', checked_response.lower())
        
        return filtered
        
    def create_emojis(self, summarized_stories):
        with open(os.path.join(self.prompt_path, 'aggregator_create_emojis_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
            
        for summary in summarized_stories:
            content = f"Story: {summary['title']}\n"
            
            for role in prompt_template:
                    if role['role'] == 'user':  
                        role['content'] = content  

            response = openai.ChatCompletion.create(
                api_key=os.environ.get('OPENAI_API_KEY'),
                model=self.config.LLM_writing_model,
                messages=prompt_template,
                max_tokens=3,
            )
            checked_response = self.check_response(response)

            summary['emoji'] = checked_response
        
        return summarized_stories
    
    def create_post(self, summarized_stories, intro, hash_tags):

        content = f"Potential post title: {intro}\n"
        content += f"Potential hashtags: {hash_tags}\n"
        for summary in summarized_stories:
            content += f"{summary['emoji']} {summary['summary']}\n"
            content += f"Alternative story title: {summary['title']}\n"
        with open(f'{self.run_output_dir}/6_output.md', 'w', encoding='UTF-8') as text_file:
            text_file.write(content)
            
        return content
