import os
import textwrap
import yaml

from .config_service import ConfigService
from .log_service import LogService
from .shelby_agent import ShelbyAgent, ShelbyAgentConfig
from sprites.discord.discord_sprite_config import DiscordSpriteConfig
from sprites.web.web_sprite_config import WebSpriteConfig

# Run for each type you want to deploy (discord or slack)
# Run after each config change before committing

# Outputs github action workflow and dockerfile

class DeploymentService():
    
    def __init__(self, deployment_config_filename):
        self.log_service = LogService('DeploymentService', 'DeploymentService.log', level='INFO')
        self.deployment_config_filename = deployment_config_filename
        
    def create_deployment(self):
        # Loads data sources from file
        with open(self.deployment_config_filename, 'r') as stream:
                self.deployment_config = yaml.safe_load(stream)
        
        secret_names = ['STACKPATH_CLIENT_ID', 'STACKPATH_API_CLIENT_SECRET', 'OPENAI_API_KEY', 'PINECONE_API_KEY', 'DOCKER_TOKEN']
        
        for moniker_dict in self.deployment_config["monikers"]:
            secrets_list = []
            env_list = []
            moniker_name = moniker_dict["moniker"]
            # deployment_config = DeploymentConfig(moniker["moniker"], self.log_service)
            for sprite, sprite_config in moniker_dict["sprites"].items():
                
                for secret in secret_names:
                    secrets_list.append(f"""{moniker_name.upper()}_{sprite.upper()}_{secret.upper()}: ${{{{ secrets.{moniker_name.upper()}_{sprite.upper()}_{secret.upper()} }}}}""")
                    
                match sprite:
                    case 'discord':
                        secrets_list.append(f"""{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN: ${{{{ secrets.{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN }}}}""")
                        
                        discord_config = DiscordSpriteConfig(moniker_name, self.log_service)
                        discord_config.create_sprite_deployment(sprite_config, self.log_service)
                        env_list = []
                        for field_name in vars(discord_config):
                            value = getattr(discord_config, field_name)
                            if value is not None:
                                env_list.append(f"""{field_name.upper()}: {value}""")
                    case 'slack':
                        secrets_list.append(f"""SLACK_BOT_TOKEN: ${{{{ secrets.{moniker_name.upper()}_SLACK_SPRITE_BOT_TOKEN }}}}""")
                        secrets_list.append(f"""SLACK_APP_TOKEN: ${{{{ secrets.{moniker_name.upper()}_SLACK_SPRITE_APP_TOKEN }}}}""")
                
        self.generate_actions_workflow(secrets_list, env_list)
            
    def generate_actions_workflow(self, secrets_list, env_list):
    
        # Positioning is required to create correct formatting. Hack work.
        
        kvps_string = '\n'.join(secrets_list)
        kvps_string = textwrap.indent(kvps_string, ' ' * 24)
        # secrets_list = [textwrap.indent(s, '\t' * 7) for s in secrets_list]

        env_string = '\n'.join(env_list)
        env_string = textwrap.indent(env_string, ' ' * 24)
                
        github_actions_script = textwrap.dedent(f"""\
        name: self.deployment_config.moniker

        on: workflow_dispatch

        jobs:
            docker:
                runs-on: ubuntu-latest
                env:
                    ### Secrets ###
                    # Secrets in the format of 'secrets.NAME'
                    # Should be added be added to github secrets as 'NAME'
                    \n{kvps_string}
                    
                    ### Container Environment Variables ###
                    \n{env_string}
                    
                    ### Github Actions Environment Variables ###
        """)
                    
                # steps:
                #     - name: Checkout code
                #         uses: actions/checkout@v3
                                        
                #     - name: Set up Python
                #         uses: actions/setup-python@v2
                #         with:
                #             python-version: '3.10.11'

                #     - name: Cache pip dependencies
                #         uses: actions/cache@v2
                #         id: cache
                #         with:
                #             path: ~/.cache/pip
                #             key: ${{{{  runner.os }}}}-pip-${{{{  hashFiles('**/app/deployment/{deployment_config.deployment_target}/{deployment_config.deployment_target}_requirements.txt') }}}}
                #             restore-keys: |
                #                 ${{{{  runner.os }}}}-pip-

                #     - name: Install dependencies
                #         run: |
                #             python -m pip install --upgrade pip
                #             if [ -f app/deployment/{deployment_config.deployment_target}/{deployment_config.deployment_target}_requirements.txt ]; then pip install -r app/deployment/{deployment_config.deployment_target}/{deployment_config.deployment_target}_requirements.txt; fi

                #     - name: Login to Docker registry
                #         uses: docker/login-action@v2 
                #         with:
                #             registry: {deployment_config.docker_registry}
                #             username: {deployment_config.docker_username}
                #             password: ${{{{  secrets.DOCKER_TOKEN }}}}

                #     - name: Build and push Docker image
                #         uses: docker/build-push-action@v4
                #         with:
                #             context: .
                #             file: app/deployment/{deployment_config.deployment_target}/Dockerfile
                #             push: true
                #             tags: {deployment_config.docker_image_path}

                #     - name: Add execute permissions to the script
                #         run: chmod +x app/deployment/deploy_stackpath_container.py

                #     - name: Run deployment script
                #         run: app/deployment/deploy_stackpath_container.py
        
        
        github_actions_script = github_actions_script.replace('    ', '  ')
        os.makedirs('.github/workflows', exist_ok=True)
        # with open(f'.github/workflows/{deployment_config.github_action_workflow_name}.yaml', 'w') as f:
        with open(f'.github/workflows/test.yaml', 'w') as f:
            f.write(github_actions_script)
                
        def generate_dockerfile():
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
                RUN pip install --no-cache-dir -r app/deployment/{deployment_config.deployment_target}/{deployment_config.deployment_target}_requirements.txt

                CMD ["python", "app/{deployment_config.deployment_target}_sprite.py"]
            """)

            os.makedirs(f'app/deployment/{deployment_config.deployment_target}', exist_ok=True)
            with open(f'app/deployment/{deployment_config.deployment_target}/Dockerfile', 'w') as f:
                f.write(dockerfile)


# DOCKER_USERNAME: {deployment_config.docker_username}
# DOCKER_REGISTRY: {deployment_config.docker_registry}
# DOCKER_SERVER: {deployment_config.docker_server}
# DOCKER_IMAGE_PATH: {deployment_config.docker_image_path}
# STACKPATH_STACK_ID: {deployment_config.stackpath_stack_id}
# DEPLOYMENT_TARGET: {deployment_config.deployment_target}
# WORKLOAD_NAME: {deployment_config.workload_name}
# WORKLOAD_SLUG: {deployment_config.workload_slug}     