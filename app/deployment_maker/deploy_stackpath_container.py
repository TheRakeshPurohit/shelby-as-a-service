#!/usr/bin/env python3

import os
import requests
import json
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

url = "https://gateway.stackpath.com/identity/v1/oauth2/token"

deployment_vars = os.environ.get('DEPLOYMENT_VARS')
deployment_vars = json.loads(deployment_vars)
deployment_name = deployment_vars['DEPLOYMENT_NAME']

headers = {"accept": "application/json", "content-type": "application/json"}
payload = {
    "grant_type": "client_credentials",
    "client_id": os.environ.get(f"{deployment_name.upper()}_STACKPATH_CLIENT_ID"),
    "client_secret": os.environ.get(f"{deployment_name.upper()}_STACKPATH_API_CLIENT_SECRET"),
}
response = requests.post(url, json=payload, headers=headers)
bearer_token = json.loads(response.text)["access_token"]
if response.status_code == 200 and bearer_token:
    print("Got bearer token.")
else:
    raise ValueError("Did not get workloads.")

url = f'https://gateway.stackpath.com/stack/v1/stacks/{deployment_vars["STACKPATH_STACK_ID"]}'
headers = {"accept": "application/json", "authorization": f"Bearer {bearer_token}"}

response = requests.get(url, headers=headers)
stack_id = json.loads(response.text)["id"]
if response.status_code == 200 and stack_id:
    print(f"Got stack_id: {stack_id}")
else:
    raise ValueError("Did not get workloads.")

# Get existing workloads
# And delete an existing workload with the same name as the one we're trying to deploy
url = f"https://gateway.stackpath.com/workload/v1/stacks/{stack_id}/workloads"
response = requests.get(url, headers=headers)
workloads = response.json()
workloads = workloads.get("results")
if response.status_code == 200 and workloads:
    print(f"Got workloads: {len(workloads)}")
else:
    raise ValueError("Did not get workloads.")
for workload in workloads:
    print(f'Existing workload name: {workload["name"]}')
    if workload["name"] == deployment_vars["WORKLOAD_NAME"].lower():
        workload_id = workload["id"]
        url = f"https://gateway.stackpath.com/workload/v1/stacks/{stack_id}/workloads/{workload_id}"
        response = requests.delete(url, headers=headers)
        if response.status_code == 204:
            print("workload deleted")
                
# Load configuration from JSON file
with open("app/deployment_maker/sp-2_container_request_template.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# Add env vars to the environment variables of the container
config["payload"]["workload"]["spec"]["containers"]["webserver"][
    "image"
] = deployment_vars["DOCKER_IMAGE_PATH"]
config["payload"]["workload"]["spec"]["imagePullCredentials"][0]["dockerRegistry"][
    "server"
] = deployment_vars["DOCKER_SERVER"]
config["payload"]["workload"]["spec"]["imagePullCredentials"][0]["dockerRegistry"][
    "username"
] = deployment_vars["DOCKER_USERNAME"]
config["payload"]["workload"]["spec"]["imagePullCredentials"][0]["dockerRegistry"][
    "password"
] = os.environ.get(f"{deployment_name.upper()}_DOCKER_TOKEN")

config["payload"]["workload"]["name"] = deployment_vars["WORKLOAD_NAME"].lower()
config["payload"]["workload"]["slug"] = deployment_vars["WORKLOAD_SLUG"].lower()

if "env" not in config["payload"]["workload"]["spec"]["containers"]["webserver"]:
    config["payload"]["workload"]["spec"]["containers"]["webserver"]["env"] = {}
    
for var, val in deployment_vars.items():
    if isinstance(val, str):
        config["payload"]["workload"]["spec"]["containers"]["webserver"]["env"].update(
            {var: {"value": val}}
        )
    else:
        val = f"'{val}'"
        config["payload"]["workload"]["spec"]["containers"]["webserver"]["env"].update(
            {var: {"value": val}}
        )
print(config)
url = f'https://gateway.stackpath.com/workload/v1/stacks/{deployment_vars["STACKPATH_STACK_ID"]}/workloads'
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": f"Bearer {bearer_token}",
}
payload = config["payload"]

# Make the API call
response = requests.post(url, json=payload, headers=headers)
if response.status_code == 200:
        print(f'{deployment_vars["WORKLOAD_NAME"].lower()} created : {response.text}')
else:
        print(f"Something went wrong creating the workload: {response.text}")
