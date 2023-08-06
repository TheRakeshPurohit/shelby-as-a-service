import os
from datetime import datetime, timedelta
from dateutil.tz import tzutc
import yaml
import math
import re
from importlib import import_module
import openai
from dotenv import load_dotenv
import tiktoken
from services.tiny_jmap_library.tiny_jmap_library import TinyJMAPClient
from services.index_service import CustomPreProcessor
from bs4 import BeautifulSoup

class Aggregator:
    def __init__(self, service_name):
        load_dotenv()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        
        self.service_name = service_name
        self.today = datetime.now().strftime('%Y_%m_%d')
        self.moniker_dir = f'app/content_aggregator/{self.service_name}'
        
        config_module_path = f"content_aggregator.{service_name}.config"
        self.config = import_module(config_module_path).MonikerAggregatorConfig
        
        self.run_output_dir = self.create_folder()
        incoming_emails = self.get_emails()
        relevant_emails = self.pre_check(incoming_emails)
        all_stories = self.split_summarize(relevant_emails)
        self.merge_stories(all_stories)
        
        print(f"Total cost: ${self.calculate_cost()}")
        
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
                            "filter": {"name": self.config.topic_folder},
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
        email_list = []
        email_count = 1
        for email in sorted_emails:
            if 'htmlBody' in email and email['htmlBody']:
                body_part_id = email["htmlBody"][0]["partId"]
            elif 'textBody' in email and email['textBody']:
                body_part_id = email["textBody"][0]["partId"]
            else:
                continue  # Skip this email if neither htmlBody nor textBody is present
            body_content = email["bodyValues"][body_part_id]["value"]

            soup = BeautifulSoup(body_content, 'html.parser')
            bs4_text_content = soup.get_text()
            
            # Removes excessive whitespace chars
            text_content = CustomPreProcessor.strip_excess_whitespace(self, bs4_text_content)
            
            email_info = {
                'subject': email['subject'],
                'number': email_count,
                'from': email['from'][0]['email'],
                'received_at': email['receivedAt'],
                'text': text_content,
                'links': [''],  # Placeholder for future implementation
            }
            email_list.append(email_info)
            email_count += 1
        emails_dict = {'emails': email_list}

        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/1_incoming_emails.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(emails_dict, yaml_file, default_flow_style=False)
        
        return emails_dict
    
    def check_response(self, response):
        # Check if keys exist in dictionary
        parsed_response = (
            response.get("choices", [{}])[0].get("message", {}).get("content")       
        )
        
        self.total_prompt_tokens += int(response.get("usage").get("prompt_tokens", 0))
        self.total_completion_tokens += int(response.get("usage").get("completion_tokens", 0))
        
        if not parsed_response:
            print(f'Error in response: {response}')
            return None

        return parsed_response
    
    def tiktoken_len(self, document):
        tokenizer = tiktoken.encoding_for_model(self.config.tiktoken_encoding_model)
        tokens = tokenizer.encode(
            document,
            disallowed_special=()
        )
        return len(tokens)
    
    def calculate_cost(self):
        prompt_cost = 0.03 * (self.total_prompt_tokens / 1000)
        completion_cost = 0.06 * (self.total_completion_tokens / 1000)
        total_cost = prompt_cost + completion_cost
        # total_cost = math.ceil(total_cost * 100) / 100
        return total_cost
        
    def pre_check(self, incoming_emails):
        
        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + 2 + 1)}
        email_list = []
        email_count = 1
        for email in incoming_emails['emails']:
            email_token_count = self.tiktoken_len(email['text'])
            print(f"email token count: {email_token_count}")
            
            if not (200 < email_token_count < 1500):
                print("email token count too small or large")
                continue
            
            content = f"Keywords: {self.config.topic_keywords}\n Text: {email['text']}"
        
            with open(os.path.join('app/prompt_templates/', 'aggregator_pre_check_template.yaml'), 'r', encoding="utf-8") as stream:
                    prompt_template = yaml.safe_load(stream)

            # Loop over the list of dictionaries in data['prompt_template']
            for role in prompt_template:
                if role['role'] == 'user':  # If the 'role' is 'user'
                    role['content'] = content  # Replace the 'content' with 'prompt_message'

            response = openai.ChatCompletion.create(
                api_key=os.environ.get('OPENAI_API_KEY'),
                model=self.config.pre_check_LLM,
                messages=prompt_template,
                max_tokens=1,
                logit_bias=logit_bias
            )

            checked_response = self.check_response(response)
            if checked_response == '1':
                print(f"{email['subject']} checks out!")
                email_info = {
                    'subject': email['subject'],
                    'number': email_count,
                    'from': email['from'],
                    'received_at': email['received_at'],
                    'text': email['text'],
                    'links': [''],  # Placeholder for future implementation
                }
                email_list.append(email_info)
                email_count += 1
                
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/2_relevant_emails.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(email_list, yaml_file, default_flow_style=False)
            
        relevant_emails = {'emails': email_list}

        return relevant_emails
    
    def split_summarize(self, relevant_emails):
        
        stories_list = []
        stories_count = 1
        
        email_count = 0
        
        for email in relevant_emails['emails']:
            email_count += 1
            if email_count >= self.config.max_emails_per_run:
                continue
            content = f"Keywords: {self.config.topic_keywords}\n Text: {email['text']}"
            
            print(f"Now splitting and summarizing: {email['subject']}")
            
            with open(os.path.join('app/prompt_templates/', 'aggregator_split_summarize_template.yaml'), 'r', encoding="utf-8") as stream:
                    prompt_template = yaml.safe_load(stream)

            # Loop over the list of dictionaries in data['prompt_template']
            for role in prompt_template:
                if role['role'] == 'user':  # If the 'role' is 'user'
                    role['content'] = content  # Replace the 'content' with 'prompt_message'

            response = openai.ChatCompletion.create(
                api_key=os.environ.get('OPENAI_API_KEY'),
                model=self.config.LLM,
                messages=prompt_template,
                max_tokens=1000,
            )

            checked_response = self.check_response(response)
            print(f'split_summarize response token count: {self.tiktoken_len(checked_response)}')
            
            # Split the text by patterns of [n], (n), n.
            pattern = r"[\[\(]\d+[\]\)]|\d+\."
            splits = re.split(pattern, checked_response)
            
            # Print each part
            for story in splits:
                
                story = CustomPreProcessor.remove_all_white_space_except_space(self, story)
                story_token_count = self.tiktoken_len(story)
                
                if  story_token_count > self.config.min_story_token_count:
                    story_info = {
                        'subject': email['subject'],
                        'number': stories_count,
                        'from': email['from'],
                        'received_at': email['received_at'],
                        'text': story,
                        'links': [''],  # Placeholder for future implementation
                    }
                    stories_list.append(story_info)
                    stories_count += 1
                
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/3_all_stories.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(stories_list, yaml_file, default_flow_style=False)
            
        all_stories = {'all_stories': stories_list}

        return all_stories
    
    def merge_stories(self, all_stories):
        
        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + 2 + 1)}
        sorted_stories = sorted(all_stories['all_stories'], key=lambda x: x['number'])
        with open(os.path.join('app/prompt_templates/', 'aggregator_merge_stories_template.yaml'), 'r', encoding="utf-8") as stream:
            prompt_template = yaml.safe_load(stream)
        
        processed_stories = {}
        all_merged_stories_list = []
        merged_stories_count = 1
        
        for active_story in sorted_stories:
            if processed_stories.get(active_story['number'], False):
                # Skip if story has been merged
                continue
            processed_stories[active_story['number']] = True
            merged_stories_list = []
            active_story_info = {
                'subject': active_story['subject'],
                'merged_story_number': merged_stories_count,
                'from': active_story['from'],
                'received_at': active_story['received_at'],
                'text': active_story['text'],
                'links': [''],  # Placeholder for future implementation
                }
            merged_stories_list.append(active_story_info)
            for comparison_story in sorted_stories:
                if processed_stories.get(comparison_story['number'], False):
                    # Skip if story has been merged
                    continue
                
                content = f"Story 1 {comparison_story['text']}\n Story 2 {active_story['text']}"
            
                # Loop over the list of dictionaries in data['prompt_template']
                for role in prompt_template:
                    if role['role'] == 'user':  # If the 'role' is 'user'
                        role['content'] = content  # Replace the 'content' with 'prompt_message'

                response = openai.ChatCompletion.create(
                    api_key=os.environ.get('OPENAI_API_KEY'),
                    model=self.config.pre_check_LLM,
                    messages=prompt_template,
                    max_tokens=1,
                    logit_bias=logit_bias
                )

                checked_response = self.check_response(response)
                
                if checked_response == '1':
                    processed_stories[comparison_story['number']] = True
                    print(f"Active story {active_story['number']} and comparison story {comparison_story['number']} match!")
                    print(f"Saving as merged story number {merged_stories_count}")
                    comparison_info = {
                        'subject': comparison_story['subject'],
                        'merged_story_number': merged_stories_count,
                        'from': comparison_story['from'],
                        'received_at': comparison_story['received_at'],
                        'text': comparison_story['text'],
                        'links': [''],  # Placeholder for future implementation
                    }
   
                    merged_stories_list.append(comparison_info)
                    
            
            merged_stories_count += 1

            all_merged_stories_list.append(merged_stories_list)
            
        # Writing the dictionary into a YAML file
        with open(f'{self.run_output_dir}/4_merged_stories.yaml', 'w', encoding='UTF-8') as yaml_file:
            yaml.dump(all_merged_stories_list, yaml_file, default_flow_style=False)
            
        merged_stories = {'merged_stories': all_merged_stories_list}

        return merged_stories