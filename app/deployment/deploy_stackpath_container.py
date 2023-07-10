#!/usr/bin/env python3

import requests
import os 
import json
import sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.agents.logger_agent import LoggerAgent

load_dotenv() 

log_agent = LoggerAgent('deploy_agent', 'deploy_agent.log', level='INFO')

DEPLOYMENT_TARGET = os.environ.get('DEPLOYMENT_TARGET')

url = "https://gateway.stackpath.com/identity/v1/oauth2/token"

headers = {
    "accept": "application/json",
    "content-type": "application/json"
}
payload = {
    "grant_type": "client_credentials",
    "client_id": os.environ.get("STACKPATH_CLIENT_ID"),
    "client_secret": os.environ.get("STACKPATH_API_CLIENT_SECRET")
}
response = requests.post(url, json=payload, headers=headers)
bearer_token = json.loads(response.text)['access_token']

# get stack id
url = f"https://gateway.stackpath.com/stack/v1/stacks/{os.environ.get('STACKPATH_STACK_ID')}"

headers = {
    "accept": "application/json",
    "authorization": f"Bearer {bearer_token}"
}

response = requests.get(url, headers=headers)
stack_id = json.loads(response.text)['id']


# Get existing workloads
url = f'https://gateway.stackpath.com/workload/v1/stacks/{stack_id}/workloads'

response = requests.get(url, headers=headers)

# And delete an existing workload with the same name as the one we're trying to deploy
if response.status_code == 200:
    workloads = response.json()
    for workload in workloads['results']:
        log_agent.print_and_log(f"Existing workload: {workload['name']}")
        if workload['name'] == os.environ.get('WORKLOAD_NAME'):
            workload_id = workload['id']
            url = f'https://gateway.stackpath.com/workload/v1/stacks/{stack_id}/workloads/{workload_id}'
            response = requests.delete(url, headers=headers)
            if response.status_code == 204:
                log_agent.print_and_log(f"{workload['name']} deleted")

# Load configuration from JSON file
with open('app/deployment/sp-2_container_request_template.json') as f:
    config = json.load(f)

# Add env vars to the environment variables of the container
config['payload']['workload']['spec']['containers']['webserver']['image'] = os.environ.get('DOCKER_IMAGE_PATH')
config['payload']['workload']['spec']['imagePullCredentials'][0]['dockerRegistry']['server'] = os.environ.get('DOCKER_SERVER')
config['payload']['workload']['spec']['imagePullCredentials'][0]['dockerRegistry']['username'] = os.environ.get('DOCKER_USERNAME')
config['payload']['workload']['spec']['imagePullCredentials'][0]['dockerRegistry']['password'] = os.environ.get('DOCKER_TOKEN')

config['payload']['workload']['name'] = os.environ.get('WORKLOAD_NAME').lower()
config['payload']['workload']['slug'] = os.environ.get('WORKLOAD_SLUG').lower()

match DEPLOYMENT_TARGET:
            case 'discord':
                config['payload']['workload']['spec']['containers']['webserver']['env'] = {
                    'DISCORD_TOKEN': {
                        'value': os.environ.get('DISCORD_TOKEN')
                    },
                    'DISCORD_CHANNEL_ID': {
                        'value': os.environ.get('DISCORD_CHANNEL_ID')
                    },
                    'DISCORD_WELCOME_MESSAGE': {
                        'value': os.environ.get('DISCORD_WELCOME_MESSAGE')
                    },
                    'DISCORD_SHORT_MESSAGE': {
                        'value': os.environ.get('DISCORD_SHORT_MESSAGE')
                    },
                    'DISCORD_MESSAGE_START': {
                        'value': os.environ.get('DISCORD_MESSAGE_START')
                    },
                    'DISCORD_MESSAGE_END': {
                        'value': os.environ.get('DISCORD_MESSAGE_END')
                    }
                }
            case 'slack':
                config['payload']['workload']['spec']['containers']['webserver']['env'] = {
                    'SLACK_BOT_TOKEN': {
                        'value': os.environ.get('SLACK_BOT_TOKEN')
                    },
                    'SLACK_APP_TOKEN': {
                        'value': os.environ.get('SLACK_APP_TOKEN')
                    }
                }
            case _:
                log_agent.print_and_log(f"TYPE not properly defined")
                
config['payload']['workload']['spec']['containers']['webserver']['env'].update({
    'OPENAI_API_KEY': {
        'value': os.environ.get('OPENAI_API_KEY')
    },
    'PINECONE_API_KEY': {
        'value': os.environ.get('PINECONE_API_KEY')
    },
    'VECTORSTORE_INDEX': {
        'value': os.environ.get('VECTORSTORE_INDEX')
    },
    'VECTORSTORE_NAMESPACES': {
        'value': os.environ.get('VECTORSTORE_NAMESPACES')
    },
    'ACTION_LLM_MODEL': {
        'value': os.environ.get('ACTION_LLM_MODEL')
    },
    'QUERY_LLM_MODEL': {
        'value': os.environ.get('QUERY_LLM_MODEL')
    },
    'VECTORSTORE_TOP_K': {
        'value': os.environ.get('VECTORSTORE_TOP_K')
    },
    'OPENAI_TIMEOUT_SECONDS': {
        'value': os.environ.get('OPENAI_TIMEOUT_SECONDS')
    },
    'MAX_DOCS_TOKENS': {
        'value': os.environ.get('MAX_DOCS_TOKENS')
    },
    'MAX_DOCS_USED': {
        'value': os.environ.get('MAX_DOCS_USED')
    },
    'MAX_RESPONSE_TOKENS': {
        'value': os.environ.get('MAX_RESPONSE_TOKENS')
    },
    'SELECT_OPERATIONID_LLM_MODEL': {
        'value': os.environ.get('SELECT_OPERATIONID_LLM_MODEL')
    },
    'CREATE_FUNCTION_LLM_MODEL': {
        'value': os.environ.get('CREATE_FUNCTION_LLM_MODEL')
    },
    'POPULATE_FUNCTION_LLM_MODEL': {
        'value': os.environ.get('POPULATE_FUNCTION_LLM_MODEL')
    },
    'TIKTOKEN_ENCODING_MODEL': {
        'value': os.environ.get('TIKTOKEN_ENCODING_MODEL')
    },
    'PROMPT_TEMPLATE_PATH': {
        'value': os.environ.get('PROMPT_TEMPLATE_PATH')
    },
    'API_SPEC_PATH': {
        'value': os.environ.get('API_SPEC_PATH')
    }
})

url = f"https://gateway.stackpath.com/workload/v1/stacks/{os.environ.get('STACKPATH_STACK_ID')}/workloads"
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": f"Bearer {bearer_token}"
}
payload = config['payload']

# Make the API call
response = requests.post(url, json=payload, headers=headers)
if response.status_code == 200:
    log_agent.print_and_log(f"{os.environ.get('WORKLOAD_NAME').lower()} created : {response.text}")
else:
    log_agent.print_and_log(f"Something went wrong creating the workload: {response.text}")


