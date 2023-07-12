import json
import os
import json
import textwrap
from configuration.shelby_agent_config import AppConfig, DeploymentConfig

# Run for each type you want to deploy (discord or slack)
# Run after each config change before committing

# Outputs github action workflow and dockerfile

def generate_workflow(deployment_target):
    deployment_config = DeploymentConfig()
    app_config = AppConfig(deployment_target)
    
    match app_config.deployment_target:
            case 'discord':
                kvps = f"""
                DISCORD_TOKEN: ${{{{ secrets.{deployment_config.service_name.upper()}_SPRITE_DISCORD_TOKEN }}}}
                DISCORD_CHANNEL_ID: ${{{{ secrets.{deployment_config.service_name.upper()}_SPRITE_DISCORD_CHANNEL_ID }}}}
                DISCORD_WELCOME_MESSAGE: {deployment_config.discord_welcome_message}
                DISCORD_SHORT_MESSAGE: {deployment_config.discord_short_message}
                DISCORD_MESSAGE_START: {deployment_config.discord_message_start}
                DISCORD_MESSAGE_END: {deployment_config.discord_message_end}
                """
            case 'slack':
                kvps = f"""
                SLACK_BOT_TOKEN: ${{{{ secrets.{deployment_config.service_name.upper()}_SPRITE_SLACK_BOT_TOKEN }}}}
                SLACK_APP_TOKEN: ${{{{ secrets.{deployment_config.service_name.upper()}_SPRITE_SLACK_APP_TOKEN }}}}
                """
                
    # Creates Github action workflow
    github_actions_script = textwrap.dedent(f"""\
    name: {app_config.github_action_workflow_name}

    on: workflow_dispatch

    jobs:
        docker:
            runs-on: ubuntu-latest
            env:
                ### Services ###
                DOCKER_USERNAME: {deployment_config.docker_username}
                DOCKER_REGISTRY: {deployment_config.docker_registry}
                DOCKER_SERVER: {app_config.docker_server}
                DOCKER_IMAGE_PATH: {app_config.docker_image_path}
                STACKPATH_STACK_ID: {deployment_config.stackpath_stack_id}
                
                ### Services Secrets to be added to github secrets ###
                STACKPATH_CLIENT_ID: ${{{{ secrets.STACKPATH_CLIENT_ID }}}}
                STACKPATH_API_CLIENT_SECRET: ${{{{ secrets.STACKPATH_API_CLIENT_SECRET }}}}
                OPENAI_API_KEY: ${{{{ secrets.OPENAI_API_KEY }}}}
                PINECONE_API_KEY: ${{{{ secrets.PINECONE_API_KEY }}}}
                DOCKER_TOKEN: ${{{{ secrets.DOCKER_TOKEN }}}}  
                {kvps}
                # Configs that may change based on deployment_target
                DEPLOYMENT_TARGET: {app_config.deployment_target}
                WORKLOAD_NAME: {app_config.workload_name}
                WORKLOAD_SLUG: {app_config.workload_slug}
                VECTORSTORE_NAMESPACES: {repr(json.dumps(app_config.vectorstore_namespaces))}               
                
                # Configs to be loaded into container env to overide config_agent
                VECTORSTORE_INDEX: {deployment_config.vectorstore_index}
                ACTION_LLM_MODEL: {deployment_config.action_llm_model}
                PRE_QUERY_LLM_MODEL: {deployment_config.pre_query_llm_model}
                QUERY_LLM_MODEL: {deployment_config.query_llm_model}
                VECTORSTORE_TOP_K: {deployment_config.vectorstore_top_k}
                OPENAI_TIMEOUT_SECONDS: {deployment_config.openai_timeout_seconds}
                MAX_DOCS_TOKENS: {deployment_config.max_docs_tokens}
                MAX_DOCS_USED: {deployment_config.max_docs_used}
                MAX_RESPONSE_TOKENS: {deployment_config.max_response_tokens}
                SELECT_OPERATIONID_LLM_MODEL: {deployment_config.select_operationID_llm_model}
                CREATE_FUNCTION_LLM_MODEL: {deployment_config.create_function_llm_model}
                POPULATE_FUNCTION_LLM_MODEL: {deployment_config.populate_function_llm_model}
    
            steps:
                - name: Checkout code
                  uses: actions/checkout@v3
                                    
                - name: Set up Python
                  uses: actions/setup-python@v2
                  with:
                      python-version: '3.10.11'

                - name: Cache pip dependencies
                  uses: actions/cache@v2
                  id: cache
                  with:
                      path: ~/.cache/pip
                      key: ${{{{  runner.os }}}}-pip-${{{{  hashFiles('**/app/deployment/{app_config.deployment_target}/{app_config.deployment_target}_requirements.txt') }}}}
                      restore-keys: |
                          ${{{{  runner.os }}}}-pip-

                - name: Install dependencies
                  run: |
                      python -m pip install --upgrade pip
                      if [ -f app/deployment/{app_config.deployment_target}/{app_config.deployment_target}_requirements.txt ]; then pip install -r app/deployment/{app_config.deployment_target}/{app_config.deployment_target}_requirements.txt; fi

                - name: Login to Docker registry
                  uses: docker/login-action@v2 
                  with:
                      registry: {deployment_config.docker_registry}
                      username: {deployment_config.docker_username}
                      password: ${{{{  secrets.DOCKER_TOKEN }}}}

                - name: Build and push Docker image
                  uses: docker/build-push-action@v4
                  with:
                      context: .
                      file: app/deployment/{app_config.deployment_target}/Dockerfile
                      push: true
                      tags: {app_config.docker_image_path}

                - name: Add execute permissions to the script
                  run: chmod +x app/deployment/deploy_stackpath_container.py

                - name: Run deployment script
                  run: app/deployment/deploy_stackpath_container.py
    """)
    
    os.makedirs('.github/workflows', exist_ok=True)
    with open(f'.github/workflows/{app_config.github_action_workflow_name}.yaml', 'w') as f:
        f.write(github_actions_script)
        
    # Generates Dockerfile
    dockerfile = textwrap.dedent(f"""\
        # Use an official Python runtime as a parent image
        FROM python:3-slim-buster
        
        # Install Git
        RUN apt-get update && apt-get install -y git
        
        # Set the working directory in the container to /shelby-as-a-service
        WORKDIR /shelby-as-a-service

        # Copy all files and folders from the root directory
        COPY ./ ./ 

        # Install python packages
        RUN pip install --no-cache-dir -r app/deployment/{app_config.deployment_target}/{app_config.deployment_target}_requirements.txt

        CMD ["python", "app/{app_config.deployment_target}_sprite.py"]
    """)

    os.makedirs(f'app/deployment/{app_config.deployment_target}', exist_ok=True)
    with open(f'app/deployment/{app_config.deployment_target}/Dockerfile', 'w') as f:
        f.write(dockerfile)

def main():
    deployment_config = AppConfig()
    for deployment_target in deployment_config.deployment_targets:
        generate_workflow(deployment_target)

main()
        
