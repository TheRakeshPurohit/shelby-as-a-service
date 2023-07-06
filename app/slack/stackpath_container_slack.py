#!/usr/bin/env python3

import requests
import os 
import json
from dotenv import load_dotenv
from configuration.shelby_agent_config import AppConfig

load_dotenv() 

agent_config = AppConfig() 

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
url = "https://gateway.stackpath.com/stack/v1/stacks/shelby-stack-327b67"

headers = {
    "accept": "application/json",
    "authorization": f"Bearer {bearer_token}"
}

response = requests.get(url, headers=headers)
stack_id = json.loads(response.text)['id']
print(stack_id)


# Load configuration from JSON file
with open('app/slack/sp-2_slack.json') as f:
    config = json.load(f)

# Add config to JSON
config['payload']['workload']['spec']['imagePullCredentials'][0]['dockerRegistry']['password'] = os.getenv('DOCKER_TOKEN')
config['payload']['workload']['name'] = agent_config.WORKLOAD_NAME
config['payload']['workload']['slug'] = agent_config.WORKLOAD_SLUG

# Add secrets to the environment variables of the container
config['payload']['workload']['spec']['containers']['webserver']['env'] = {
    'OPENAI_API_KEY': {
        'value': os.getenv('OPENAI_API_KEY')
    },
    'PINECONE_API_KEY': {
        'value': os.getenv('PINECONE_API_KEY')
    },
    'SLACK_BOT_TOKEN': {
        'value': os.getenv('SLACK_BOT_TOKEN')
    },
    'SLACK_APP_TOKEN': {
        'value': os.getenv('SLACK_APP_TOKEN')
    },
    'VECTORSTORE_INDEX': {
        'value': agent_config.vectorstore_index
    },
    'NAMESPACES': {
        'value': agent_config.vectorstore_namespaces
    }
}

url = "https://gateway.stackpath.com/workload/v1/stacks/shelby-stack-327b67/workloads"
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": f"Bearer {bearer_token}"
}
payload = config['payload']

# Make the API call
response = requests.post(url, json=payload, headers=headers)

# Print the response
print(response.text)

