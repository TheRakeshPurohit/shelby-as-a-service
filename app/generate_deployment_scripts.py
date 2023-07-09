import json
import os
import json
import textwrap
from configuration.shelby_agent_config import AppConfig

# Run for each type you want to deploy (discord or slack)
# Run after each config change before committing

# Outputs github action workflow and dockerfile

def generate_workflow():
    agent_config = AppConfig()
    
    if agent_config.TYPE == 'discord':
        kvp_1 = f'DISCORD_TOKEN: ${{{{ secrets.{agent_config.NAME.upper()}_SPRITE_DISCORD_TOKEN }}}}'
        kvp_2 = f'DISCORD_CHANNEL_ID: ${{{{ secrets.{agent_config.NAME.upper()}_SPRITE_DISCORD_CHANNEL_ID }}}}'
    elif agent_config.TYPE == 'slack':
        kvp_1 = f'SLACK_BOT_TOKEN: ${{{{ secrets.{agent_config.NAME.upper()}_SPRITE_SLACK_BOT_TOKEN }}}}'
        kvp_2 = f'SLACK_APP_TOKEN: ${{{{ secrets.{agent_config.NAME.upper()}_SPRITE_SLACK_APP_TOKEN }}}}'
        
    # Creates Github action workflow
    github_actions_script = textwrap.dedent(f"""\
    name: {agent_config.GITHUB_ACTION_WORKFLOW_NAME}

    on: workflow_dispatch

    jobs:
        docker:
            runs-on: ubuntu-latest
            env:
                # Required github secrets
                STACKPATH_CLIENT_ID: ${{{{ secrets.STACKPATH_CLIENT_ID }}}}
                STACKPATH_API_CLIENT_SECRET: ${{{{ secrets.STACKPATH_API_CLIENT_SECRET }}}}
                OPENAI_API_KEY: ${{{{ secrets.OPENAI_API_KEY }}}}
                PINECONE_API_KEY: ${{{{ secrets.PINECONE_API_KEY }}}}
                DOCKER_TOKEN: ${{{{ secrets.DOCKER_TOKEN }}}}
                
                {kvp_1}
                {kvp_2}
                
                DOCKER_USERNAME: {agent_config.DOCKER_USERNAME}
                DOCKER_REGISTRY: {agent_config.DOCKER_REGISTRY}
                DOCKER_SERVER: {agent_config.DOCKER_SERVER}
                DOCKER_IMAGE_PATH: {agent_config.DOCKER_IMAGE_PATH}
                
                STACKPATH_STACK_ID: {agent_config.STACKPATH_STACK_ID}
                
                TYPE: {agent_config.TYPE}
                WORKLOAD_NAME: {agent_config.WORKLOAD_NAME}
                WORKLOAD_SLUG: {agent_config.WORKLOAD_SLUG}
                VECTORSTORE_INDEX: {agent_config.vectorstore_index}
                VECTORSTORE_NAMESPACES: {repr(json.dumps(agent_config.vectorstore_namespaces))}
                
                ACTION_LLM_MODEL: {agent_config.action_llm_model}
                QUERY_LLM_MODEL: {agent_config.query_llm_model}
                VECTORSTORE_TOP_K: {agent_config.vectorstore_top_k}
                OPENAI_TIMEOUT_SECONDS: {agent_config.openai_timeout_seconds}
                MAX_DOCS_TOKENS: {agent_config.max_docs_tokens}
                MAX_DOCS_USED: {agent_config.max_docs_used}
                MAX_RESPONSE_TOKENS: {agent_config.max_response_tokens}
                SELECT_OPERATIONID_LLM_MODEL: {agent_config.select_operationID_llm_model}
                CREATE_FUNCTION_LLM_MODEL: {agent_config.create_function_llm_model}
                POPULATE_FUNCTION_LLM_MODEL: {agent_config.populate_function_llm_model}
                TIKTOKEN_ENCODING_MODEL: {agent_config.tiktoken_encoding_model}
                PROMPT_TEMPLATE_PATH: {agent_config.prompt_template_path}
                API_SPEC_PATH: {agent_config.API_spec_path}
    
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
                      key: ${{{{  runner.os }}}}-pip-${{{{  hashFiles('**/app/deployment/{agent_config.TYPE}/{agent_config.TYPE}_requirements.txt') }}}}
                      restore-keys: |
                          ${{{{  runner.os }}}}-pip-

                - name: Install dependencies
                  run: |
                      python -m pip install --upgrade pip
                      if [ -f app/deployment/{agent_config.TYPE}/{agent_config.TYPE}_requirements.txt ]; then pip install -r app/deployment/{agent_config.TYPE}/{agent_config.TYPE}_requirements.txt; fi

                - name: Login to Docker registry
                  uses: docker/login-action@v2 
                  with:
                      registry: {agent_config.DOCKER_REGISTRY}
                      username: {agent_config.DOCKER_USERNAME}
                      password: ${{{{  secrets.DOCKER_TOKEN }}}}

                - name: Build and push Docker image
                  uses: docker/build-push-action@v4
                  with:
                      context: .
                      file: app/deployment/{agent_config.TYPE}/Dockerfile
                      push: true
                      tags: {agent_config.DOCKER_IMAGE_PATH}

                - name: Add execute permissions to the script
                  run: chmod +x app/deployment/deploy_stackpath_container.py

                - name: Run deployment script
                  run: app/deployment/deploy_stackpath_container.py
    """)
    
    os.makedirs('.github/workflows', exist_ok=True)
    with open(f'.github/workflows/{agent_config.GITHUB_ACTION_WORKFLOW_NAME}.yaml', 'w') as f:
        f.write(github_actions_script)
        
    # Generates Dockerfile
    dockerfile = textwrap.dedent(f"""\
        # Use an official Python runtime as a parent image
        FROM python:3-slim-buster

        # Set the working directory in the container to /shelby-as-a-service
        WORKDIR /shelby-as-a-service

        # Copy all files and folders from the root directory
        COPY ./ ./ 

        # Install python packages
        RUN pip install --no-cache-dir -r app/deployment/{agent_config.TYPE}/{agent_config.TYPE}_requirements.txt

        CMD ["python", "app/{agent_config.TYPE}_sprite.py"]
    """)

    os.makedirs('app/deployment/discord', exist_ok=True)
    with open(f'app/deployment/{agent_config.TYPE}/Dockerfile', 'w') as f:
        f.write(dockerfile)

generate_workflow()
