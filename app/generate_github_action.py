import json
from configuration.shelby_agent_config import AppConfig
import textwrap
import os

def generate_workflow():
    agent_config = AppConfig() 
    template = textwrap.dedent(f"""\
    name: {agent_config.GITHUB_ACTION_WORKFLOW_NAME}
    
    # Requried github secrets
    # STACKPATH_CLIENT_ID 
    # STACKPATH_API_CLIENT_SECRET
    # OPENAI_API_KEY
    # PINECONE_API_KEY
    # DOCKER_USERNAME
    # DOCKER_TOKEN
    # {agent_config.NAME.upper()}_SPRITE_DISCORD_TOKEN
    # {agent_config.NAME.upper()}_SPRITE_DISCORD_CHANNEL_ID

    on: workflow_dispatch

    jobs:
        docker:
            runs-on: ubuntu-latest
            env:
                STACKPATH_CLIENT_ID: ${{{{ secrets.STACKPATH_CLIENT_ID }}}}
                STACKPATH_API_CLIENT_SECRET: ${{{{ secrets.STACKPATH_API_CLIENT_SECRET }}}}
                OPENAI_API_KEY: ${{{{ secrets.OPENAI_API_KEY }}}}
                PINECONE_API_KEY: ${{{{ secrets.PINECONE_API_KEY }}}}
                DOCKER_USERNAME: ${{{{ secrets.DOCKER_USERNAME }}}}
                DOCKER_TOKEN: ${{{{ secrets.DOCKER_TOKEN }}}}
                DISCORD_TOKEN: ${{{{ secrets.{agent_config.NAME.upper()}_SPRITE_DISCORD_TOKEN }}}}
                DISCORD_CHANNEL_ID: ${{{{ secrets.{agent_config.NAME.upper()}_SPRITE_DISCORD_CHANNEL_ID }}}}
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
                      key: ${{{{  runner.os }}}}-pip-${{{{  hashFiles('**/requirements.txt') }}}}
                      restore-keys: |
                          ${{{{  runner.os }}}}-pip-

                - name: Install dependencies
                  run: |
                      python -m pip install --upgrade pip
                      if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

                - name: Login to Docker registry
                  uses: docker/login-action@v2 
                  with:
                      registry: docker.io 
                      username: ${{{{ secrets.DOCKER_USERNAME }}}}
                      password: ${{{{  secrets.DOCKER_TOKEN }}}}

                - name: Build and push Docker image
                  uses: docker/build-push-action@v4
                  with:
                      context: .
                      file: app/discord/Dockerfile
                      push: true
                      tags: shelbyjenkins/shelby-as-a-service:discord-latest

                - name: Add execute permissions to the script
                  run: chmod +x app/discord/stackpath_container_discord.py

                - name: Run deployment script
                  run: app/discord/stackpath_container_discord.py
    """)
    
    os.makedirs('.github/workflows', exist_ok=True)
    with open(f'.github/workflows/{agent_config.GITHUB_ACTION_WORKFLOW_NAME}.yaml', 'w') as f:
        f.write(template)

generate_workflow()
