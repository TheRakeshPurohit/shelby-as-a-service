import os
import textwrap
import yaml

from services.config_service import DeploymentRequiredConfigs
from sprites.discord.discord_sprite_config import DiscordSpriteConfig
# from .index_service import IndexService
# from sprites.web.web_sprite_config import WebSpriteConfig

# Outputs github action workflow and dockerfile

class DeploymentService():
    
    def __init__(self, deployment_settings_filename, log_service):
        self.log_service = log_service
        with open(deployment_settings_filename, 'r') as stream:
                self.deployment_settings = yaml.safe_load(stream)
        self.deployment_env = DeploymentServicesRequiredEnvs(self.deployment_settings, self.log_service)
        self.deployment_name = self.deployment_settings["deployment_name"]
        
    def create_deployment_from_file(self):
        
        self.generate_dockerfile()
        self.generate_shell_script()
        self.generate_pip_requirements()
        env_list, secrets_list = self.populate_variables()
        self.generate_actions_workflow(env_list, secrets_list)
        
    def generate_dockerfile(self):
        

        dockerfile = f"""\
# Use an official Python runtime as a parent image
FROM python:3-slim-buster

# Install Git
RUN apt-get update && apt-get install -y git

# Set the working directory in the container to /shelby-as-a-service
WORKDIR /shelby-as-a-service

# Copy all files and folders from the root directory
COPY ./ ./ 

# Install python packages
RUN pip install --no-cache-dir -r app/deploy/automation/{self.deployment_name}/requirements.txt

# Run Sprites
CMD ["/bin/bash", "app/deploy/automation/{self.deployment_name}/startup.sh"]
        """

        os.makedirs(f'app/deploy/automation/{self.deployment_name}', exist_ok=True)
        with open(f'app/deploy/automation/{self.deployment_name}/Dockerfile', 'w') as f:
            f.write(dockerfile)

    def generate_shell_script(self):
        scripts_string = ''
        for moniker, moniker_config in self.deployment_settings["monikers"].items():
            for sprite in moniker_config["sprites"]:
                scripts_string += f'python app/run.py --deployment {self.deployment_name} {moniker} {sprite} &\n'

        script_content = f"""\
#!/bin/bash
# start_up.sh

# Start scripts in background
{scripts_string}

# Wait for all background processes to finish
wait
"""

        os.makedirs(f'app/deploy/automation/{self.deployment_name}', exist_ok=True)
        with open(f'app/deploy/automation/{self.deployment_name}/startup.sh', 'w') as f:
            f.write(script_content)

    def generate_pip_requirements(self):
        self.unique_platforms = {sprite for moniker_config in self.deployment_settings["monikers"].values() for sprite in moniker_config["sprites"].keys()}

        combined_requirements = set()

        for platform in self.unique_platforms:
            with open(f'app/deploy/automation/{platform}_requirements.txt') as file:
                platform_requirements = set(file.read().splitlines())
            combined_requirements.update(platform_requirements)

        os.makedirs(f'app/deploy/automation/{self.deployment_name}', exist_ok=True)
        with open(f'app/deploy/automation/{self.deployment_name}/requirements.txt', 'w') as file:
            file.write('\n'.join(combined_requirements))

    def generate_actions_workflow(self, env_list, secrets_list):
    
        # Positioning is required to create correct formatting. Hack work.
        secrets_string = '\n'.join(secrets_list)
        secrets_string = textwrap.indent(secrets_string, ' ' * 24)

        env_string = '\n'.join(env_list)
        env_string = textwrap.indent(env_string, ' ' * 24)
                
        github_actions_script = textwrap.dedent(f"""\
        name: {self.deployment_env.github_action_workflow_name}

        on: workflow_dispatch

        jobs:
            docker:
                runs-on: ubuntu-latest
                env:
                        ### Secrets ###
                        # Secrets in the format of 'secrets.NAME'
                        # Should be added be added to github secrets as 'NAME'
                    \n{secrets_string}
                    \n{env_string}
                    
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
                            key: ${{{{  runner.os }}}}-pip-${{{{  hashFiles('**app/deploy/automation/{self.deployment_name}/requirements.txt') }}}}
                            restore-keys: |
                                ${{{{  runner.os }}}}-pip-

                    - name: Install dependencies
                        run: |
                            python -m pip install --upgrade pip
                            if [ -f app/deploy/automation/{self.deployment_name}/requirements.txt ]; then pip install -r app/deploy/automation/{self.deployment_name}/requirements.txt; fi

                    - name: Login to Docker registry
                        uses: docker/login-action@v2 
                        with:
                            registry: {self.deployment_env.docker_registry}
                            username: {self.deployment_env.docker_username}
                            password: ${{{{  secrets.DOCKER_TOKEN }}}}

                    - name: Build and push Docker image
                        uses: docker/build-push-action@v4
                        with:
                            context: .
                            file: app/deployment/{self.deployment_name}/Dockerfile
                            push: true
                            tags: {self.deployment_env.docker_image_path}

                    - name: Add execute permissions to the script
                        run: chmod +x app/deploy/automation/deploy_stackpath_container.py

                    - name: Run deployment script
                        run: app/deploy/automation/deploy_stackpath_container.py
        """)
        
        github_actions_script = github_actions_script.replace('    ', '  ')
        os.makedirs('.github/workflows', exist_ok=True)
        # with open(f'.github/workflows/{deployment_settings.github_action_workflow_name}.yaml', 'w') as f:
        with open(f'.github/workflows/{self.deployment_name}_deployment.yaml', 'w') as f:
            f.write(github_actions_script)
                
    def populate_variables(self):
        
        secrets_list= []
        env_list= []
        secrets_list = self.generate_default_secrets(secrets_list)
        # For Each Moniker
        for moniker_name, moniker_config in self.deployment_settings["monikers"].items():
            env_list.append(f'\n### {moniker_name}_environment_variables ###\n')
            # For each Sprite
            for platform, sprite_config in moniker_config["sprites"].items():
                env_list= []
                match platform:
                    case 'discord':
                        secrets_list.append(f"""{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN: ${{{{ secrets.{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN }}}}""")
                        discord_config = DiscordSpriteConfig()
                        discord_config.create_discord_deployment(moniker_name, sprite_config, self.log_service)

                        for field_name in vars(discord_config):
                            value = getattr(discord_config, field_name)
                            if value is not None:
                                env_list.append(f"""{moniker_name.upper()}_{platform.upper()}_{field_name.upper()}: {value}""")
                                
                    case 'slack':
                        secrets_list.append(f"""{moniker_name.upper()}_SLACK_BOT_TOKEN: ${{{{ secrets.{moniker_name.upper()}_SLACK_SPRITE_BOT_TOKEN }}}}""")
                        secrets_list.append(f"""{moniker_name.upper()}_SLACK_APP_TOKEN: ${{{{ secrets.{moniker_name.upper()}_SLACK_SPRITE_APP_TOKEN }}}}""")
                        
        env_list.append('### deployment_services_environment_variables ###\n')
        for field_name in vars(self.deployment_env):
            value = getattr(self.deployment_env, field_name)
            if value is not None:
                env_list.append(f"""{field_name.upper()}: {value}""")
        
        env_list.append('\n### config_overrides_variables ###\n')
        for override_name, override_value in self.deployment_settings["config_overrides"].items():
            env_list.append(f"""{override_name.upper()}: {override_value}""")
    
        return env_list, secrets_list
    
    def generate_default_secrets(self, secrets_list):
        
        secret_names = ['STACKPATH_CLIENT_ID', 'STACKPATH_API_CLIENT_SECRET', 'OPENAI_API_KEY', 'PINECONE_API_KEY', 'DOCKER_TOKEN']
        for secret in secret_names:
            secrets_list.append(f"""{secret.upper()}: ${{{{ secrets.{secret.upper()} }}}}""")
        
        return secrets_list
        
class DeploymentServicesRequiredEnvs:
    
    def __init__(self, deployment_settings, log_service):
        ### Everything here can be set by file ###
        self.docker_registry: str = ''
        self.docker_username: str = ''
        self.docker_repo: str = ''
        self.stackpath_stack_id: str = ''
        DeploymentRequiredConfigs(self, deployment_settings["deployment_services"], log_service)
        
        self.docker_server: str = f'{self.docker_registry}/{self.docker_username}/{self.docker_repo}'
        self.docker_image_path: str = f'{self.docker_username}/{self.docker_repo}:{deployment_settings["deployment_name"]}-latest'
        self.github_action_workflow_name: str = f'deploy-{deployment_settings["deployment_name"]}'
        self.workload_name: str = f'{deployment_settings["deployment_name"]}-workload'
        self.workload_slug: str = f'{deployment_settings["deployment_name"]}-slug'