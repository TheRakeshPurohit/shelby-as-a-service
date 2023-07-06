#!/usr/bin/env python3

import requests
import os 
import json
from dotenv import load_dotenv
from configuration.shelby_agent_config import AppConfig
from agents.logger_agent import LoggerAgent

load_dotenv() 

agent_config = AppConfig() 
log_agent = LoggerAgent('deploy_agent', 'deploy_agent.log', level='INFO')

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


# Get existing workloads
url = f'https://gateway.stackpath.com/workload/v1/stacks/{stack_id}/workloads'

response = requests.get(url, headers=headers)

# And delete an existing workload with the same name as the one we're trying to deploy
if response.status_code == 200:
    workloads = response.json()
    for workload in workloads['results']:
        log_agent.print_and_log(f"Existing workload: {workload['name']}")
        if workload['name'] == agent_config.WORKLOAD_NAME:
            workload_id = workload['id']
            url = f'https://gateway.stackpath.com/workload/v1/stacks/{stack_id}/workloads/{workload_id}'
            response = requests.delete(url, headers=headers)
            if response.status_code == 204:
                log_agent.print_and_log(f"{workload['name']} deleted")

# Load configuration from JSON file
with open('app/discord/sp-2_discord.json') as f:
    config = json.load(f)

config['payload']['workload']['spec']['imagePullCredentials'][0]['dockerRegistry']['password'] = os.getenv('DOCKER_TOKEN')
config['payload']['workload']['name'] = agent_config.WORKLOAD_NAME.lower()
config['payload']['workload']['slug'] = agent_config.WORKLOAD_SLUG.lower()

# Add secrets to the environment variables of the container
config['payload']['workload']['spec']['containers']['webserver']['env'] = {
    'OPENAI_API_KEY': {
        'value': os.getenv('OPENAI_API_KEY')
    },
    'PINECONE_API_KEY': {
        'value': os.getenv('PINECONE_API_KEY')
    },
    'DISCORD_TOKEN': {
        'value': os.getenv('DISCORD_TOKEN')
    },
    'DISCORD_CHANNEL_ID': {
        'value': os.getenv('DISCORD_CHANNEL_ID')
    },
    'VECTORSTORE_INDEX': {
        'value': agent_config.vectorstore_index
    },
    'VECTORSTORE_NAMESPACES': {
        'value': json.dumps(agent_config.vectorstore_namespaces)
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
if response.status_code == 200:
    log_agent.print_and_log(f"{agent_config.WORKLOAD_NAME} created : {response.text}")
else:
    log_agent.print_and_log(f"Something went wrong creating the workload: {response.text}")


