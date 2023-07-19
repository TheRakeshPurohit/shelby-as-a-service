import json
import os
import json
import textwrap
from pydantic import BaseModel, Field
from agents.config_agent import YourConfig, DeploymentConfig
from agents.log_agent import LoggerAgent

# Run for each type you want to deploy (discord or slack)
# Run after each config change before committing

# Outputs github action workflow and dockerfile

class DeploymentAgent():
    
    def __init__(self):

        self.your_config= YourConfig()
        self.log_agent = LoggerAgent('DeploymentAgent', 'DeploymentAgent.log', level='INFO')
        
    def generate_deployments(self):
    
        for deployment_target in self.your_config.deployment_targets:
            deployment_config = DeploymentConfig(self.your_config, deployment_target, self.log_agent)
            self._generate_deployment(deployment_config, deployment_target)
    
    def _generate_deployment(self, deployment_config: DeploymentConfig, deployment_target: str):
        
        def _generate_github_action():
            # Positioning is required to create correct formatting. Hack work.
            secrets_kvps = ""
            for secret in deployment_config.your_config.secret_names:
                secrets_kvps += f"""{secret}: ${{{{ secrets.{secret} }}}}
                        """
            match deployment_target:
                case 'discord':
                    secrets_kvps += f"""DISCORD_TOKEN: ${{{{ secrets.{deployment_config.sprite_name.upper()}_SPRITE_DISCORD_TOKEN }}}}"""
                case 'slack':
                    secrets_kvps += f"""SLACK_BOT_TOKEN: ${{{{ secrets.{deployment_config.sprite_name.upper()}_SPRITE_SLACK_BOT_TOKEN }}}}
                        SLACK_APP_TOKEN: ${{{{ secrets.{deployment_config.sprite_name.upper()}_SPRITE_SLACK_APP_TOKEN }}}}"""
            env_kvps = ""
            for field_name in vars(deployment_config.deployment_envs):
                value = getattr(deployment_config.deployment_envs, field_name)
                if value is not None:
                    env_kvps += f"""{field_name.upper()}: {value}
                        """
            github_actions_script = textwrap.dedent(f"""\
            name: {deployment_config.github_action_workflow_name}

            on: workflow_dispatch

            jobs:
                docker:
                    runs-on: ubuntu-latest
                    env:
                        ### Secrets ###
                        # Secrets in the format of '${{{{ secrets.NAME }}}}'
                        # Should be added be added to github secrets as 'NAME' 
                        {secrets_kvps}
                        
                        ### Container Environment Variables ###
                        {env_kvps}
                        ### Github Actions Environment Variables ###
                        DOCKER_USERNAME: {deployment_config.docker_username}
                        DOCKER_REGISTRY: {deployment_config.docker_registry}
                        DOCKER_SERVER: {deployment_config.docker_server}
                        DOCKER_IMAGE_PATH: {deployment_config.docker_image_path}
                        STACKPATH_STACK_ID: {deployment_config.stackpath_stack_id}
                        DEPLOYMENT_TARGET: {deployment_config.deployment_target}
                        WORKLOAD_NAME: {deployment_config.workload_name}
                        WORKLOAD_SLUG: {deployment_config.workload_slug}         
                        
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
                            key: ${{{{  runner.os }}}}-pip-${{{{  hashFiles('**/app/deployment/{deployment_config.deployment_target}/{deployment_config.deployment_target}_requirements.txt') }}}}
                            restore-keys: |
                                ${{{{  runner.os }}}}-pip-

                        - name: Install dependencies
                        run: |
                            python -m pip install --upgrade pip
                            if [ -f app/deployment/{deployment_config.deployment_target}/{deployment_config.deployment_target}_requirements.txt ]; then pip install -r app/deployment/{deployment_config.deployment_target}/{deployment_config.deployment_target}_requirements.txt; fi

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
                            file: app/deployment/{deployment_config.deployment_target}/Dockerfile
                            push: true
                            tags: {deployment_config.docker_image_path}

                        - name: Add execute permissions to the script
                        run: chmod +x app/deployment/deploy_stackpath_container.py

                        - name: Run deployment script
                        run: app/deployment/deploy_stackpath_container.py
            """)
        
            os.makedirs('.github/workflows', exist_ok=True)
            with open(f'.github/workflows/{deployment_config.github_action_workflow_name}.yaml', 'w') as f:
                f.write(github_actions_script)
        
        def _generate_dockerfile():
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

        _generate_github_action()
        _generate_dockerfile()
