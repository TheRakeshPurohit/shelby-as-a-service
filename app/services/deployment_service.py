import os
import textwrap
import yaml
import traceback
from services.config_service import DeploymentRequiredConfigs
from services.shelby_agent import ShelbyAgent
from sprites.discord_sprite import DiscordSprite

# from .index_service import IndexService
# from sprites.web.web_sprite_config import WebSpriteConfig

from services.base_class import BaseClass

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
        deploy_env_list, local_env_list, deploy_secrets_list, local_secrets_list = self.populate_variables()
        self.generate_actions_workflow(deploy_env_list , deploy_secrets_list)
        # self.generate_local_env_file(local_env_list, local_secrets_list)
        
        # self.docker_server: str = f'{self.docker_registry}/{self.docker_username}/{self.docker_repo}'
        # self.docker_image_path: str = f'{self.docker_username}/{self.docker_repo}:{deployment_settings["deployment_name"]}-latest'
        # self.github_action_workflow_name: str = f'deploy-{deployment_settings["deployment_name"]}'
        # self.workload_name: str = f'{deployment_settings["deployment_name"]}-workload'
        # self.workload_slug: str = f'{deployment_settings["deployment_name"]}-slug'
        
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

    def generate_actions_workflow(self, deploy_env_list , deploy_secrets_list):
    
        # Positioning is required to create correct formatting. Hack work.
        secrets_string = '\n'.join(deploy_secrets_list)
        secrets_string = textwrap.indent(secrets_string, ' ' * 24)

        env_string = '\n'.join(deploy_env_list )
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
        
        deploy_env_list = []
        local_env_list = []
        deploy_secrets_list, local_secrets_list = self.generate_default_secrets()
        # For Each Moniker
        for moniker_name, moniker_config in self.deployment_settings["monikers"].items():
            deploy_env_list.append(f'\n### {moniker_name}_environment_variables ###\n')
            local_env_list.append(f'\n### {moniker_name}_environment_variables ###\n')
            # For each Sprite
            for platform, sprite_config in moniker_config["sprites"].items():
                match platform:
                    case 'discord':
                        deploy_secrets_list.append(f"""{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN: ${{{{ secrets.{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN }}}}""")
                        local_secrets_list.append(f"""{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN=""")
                        discord_config = DiscordSpriteConfig()
                        discord_config.create_discord_deployment(moniker_name, sprite_config, self.log_service)

                        for field_name in vars(discord_config):
                            value = getattr(discord_config, field_name)
                            if value is not None:
                                deploy_env_list.append(f"""{moniker_name.upper()}_{platform.upper()}_{field_name.upper()}: {value}""")
                                local_env_list.append(f"""{moniker_name.upper()}_{platform.upper()}_{field_name.upper()}={value}""")
                                
                    case 'slack':
                        deploy_secrets_list.append(f"""{moniker_name.upper()}_SLACK_BOT_TOKEN: ${{{{ secrets.{moniker_name.upper()}_SLACK_SPRITE_BOT_TOKEN }}}}""")
                        local_secrets_list.append(f"""{moniker_name.upper()}_SLACK_BOT_TOKEN=""")
                        deploy_secrets_list.append(f"""{moniker_name.upper()}_SLACK_APP_TOKEN: ${{{{ secrets.{moniker_name.upper()}_SLACK_SPRITE_APP_TOKEN }}}}""")
                        local_secrets_list.append(f"""{moniker_name.upper()}_SLACK_APP_TOKEN=""")
                        
        deploy_env_list.append('\n### deployment_services_environment_variables ###\n')
        local_env_list.append('\n### deployment_services_environment_variables ###\n')
        for field_name in vars(self.deployment_env):
            value = getattr(self.deployment_env, field_name)
            if value is not None:
                deploy_env_list.append(f"""{field_name.upper()}: {value}""")
                local_env_list.append(f"""{field_name.upper()}={value}""")
        
        deploy_env_list.append('\n### config_overrides_variables ###\n')
        local_env_list.append('\n### config_overrides_variables ###\n')
        for override_name, override_value in self.deployment_settings["config_overrides"].items():
            deploy_env_list.append(f"""{override_name.upper()}: {override_value}""")
            local_env_list.append(f"""{override_name.upper()}={override_value}""")
    
        return deploy_env_list, local_env_list, deploy_secrets_list, local_secrets_list
    
    def generate_default_secrets(self):
        deploy_secrets_list = []
        local_secrets_list = []
        secret_names = ['STACKPATH_CLIENT_ID', 'STACKPATH_API_CLIENT_SECRET', 'OPENAI_API_KEY', 'PINECONE_API_KEY', 'DOCKER_TOKEN']
        for secret in secret_names:
            deploy_secrets_list.append(f"""{secret.upper()}: ${{{{ secrets.{secret.upper()} }}}}""")
            local_secrets_list.append(f"""{secret.upper()}=""")
        
        return deploy_secrets_list, local_secrets_list
    
class ConfigBuilder(BaseClass):
    
    def __init__(self, new_deployment_name):
        self.deployment_name = new_deployment_name
    def create_config(self):
        
        config_file = {
            'deployment_name': self.deployment_name,
            'moniker_level_variables': False,
            'monikers': [
                {
                    'name': 'your_first_moniker',
                    'sprites': {
                        'discord': True,
                        'slack': False,
                        'web': False,
                    }
                },
                {
                    'name': 'your_second_moniker',
                    'sprites': {
                        'discord': True,
                        'slack': True,
                        'web': True,
                    }
                }
            ]
        }

        os.makedirs(f'app/deployments/{self.deployment_name}', exist_ok=True)
        with open(f'app/deployments/{self.deployment_name}/{self.deployment_name}_config.yaml', 'w') as outfile:
            yaml.dump(config_file, outfile, default_flow_style=False)

    def create_template(self):
        try:
            services = set([ShelbyAgent])
            
            with open(f'app/deployments/{self.deployment_name}/{self.deployment_name}_config.yaml', 'r') as infile:
                self.config = yaml.safe_load(infile)
            
            # Switch to enable extra variables    
            moniker_level_variables = self.config['moniker_level_variables']
            monikers = []
            sprites = set()
            for moniker in self.config['monikers']:
                moniker_name = moniker['name']
                monikers.append(moniker_name)
                for sprite_name, sprite_value in moniker['sprites'].items():
                    if sprite_value is True:
                        match sprite_name:
                            case 'discord':
                                sprite = DiscordSprite
                            # case 'web':
                            #     sprite = WebSprite
                            # case 'slack':
                            #     sprite = SlackSprite
                            case _:
                                continue
                        sprites.add(sprite)
            # Intro
            self.env_list = []
            self.env_list.append('### Deployment level Variables ###\n')
            self.iterate_base_class()
            self.iterate_sprites_deployment_level(sprites, services)
            # If moniker_level_variables is True
            if moniker_level_variables:
                for moniker in monikers:
                    self.env_list.append(f'\n### Moniker level variables ###\n')
                    self.env_list.append(f'\t## {moniker.upper()} level ##\n')
                    self.env_list.append('\t\t# Required here or at deployment level or in sprite variables #')
                    class_vars = [var for var in vars(BaseClass) if not var in BaseClass._DEVOPS_VARIABLES]
                    for var in class_vars:
                        if not (var.startswith('_') or callable(getattr(BaseClass, var))):
                            self.env_list.append(f'\t\t{self.deployment_name.upper()}_{moniker.upper()}_{var.upper()}=')
                    self.iterate_sprites_moniker_level(sprites, services, moniker)
            self.env_list.append(f'\nDEPLOYMENT_POPULATED=False')
                
            env_string = '\n'.join(self.env_list)
            env_string = textwrap.indent(env_string, ' ' * 24)
                    
            local_env_file = textwrap.dedent(f"""\
{env_string}
            """)

            os.makedirs(f'app/deployments/{self.deployment_name}', exist_ok=True)
            with open(f'app/deployments/{self.deployment_name}/{self.deployment_name}.env', 'w') as f:
                f.write(local_env_file)
            
        except Exception as error:
            error_info = traceback.format_exc()
            print('Error: config.yaml must have at least one moniker and at least one sprite.')
            print(f'{error}\n{error_info}')
            raise
    
    def iterate_base_class(self):
        # Add used vars to list, and skip if they've been used
        used_vars = []
        self.env_list.append('\t## Devops variables only set at deployment level ##\n')
        self.env_list.append('\t\t# These are required to deploy to container #')
        self.env_list.append(f'\t\tDEPLOYMENT_NAME={self.deployment_name}')
        for var in BaseClass._DEVOPS_VARIABLES :
            self.env_list.append(f'\t\t{self.deployment_name.upper()}_{var.upper()}=')
            used_vars.append(var)
        self.env_list.append('\n\t\t# Required here or in sprite variables #')
        for var, _ in vars(BaseClass).items() :
            if not (var.startswith('_') or callable(getattr(BaseClass, var)) or var in used_vars):
                self.env_list.append(f'\t\t{self.deployment_name.upper()}_{var.upper()}=')
                     
    def iterate_sprites_deployment_level(self, sprites, services):
        for sprite in sprites:
            used_vars = []
            self.env_list.append(f'\n\t## {sprite.__name__.upper()} Variables ##\n')
            self.env_list.append('\t\t# Required here #')
            for var in sprite._SECRET_VARIABLES:
                self.env_list.append(f'\t\t{self.deployment_name.upper()}_{sprite.__name__.upper()}_{var.upper()}=')
                used_vars.append(var)
                
            self.env_list.append('\n\t\t# Required here or at deployment level #')
            for service in services:
                for var in service._SECRET_VARIABLES:
                    self.env_list.append(f'\t\t{self.deployment_name.upper()}_{sprite.__name__.upper()}_{var.upper()}=')
                    used_vars.append(var)
                    
            self.env_list.append('\n\t\t# Recommended #')
            for var, val in vars(sprite).items():
                if not (var.startswith('_') or callable(getattr(sprite, var)) or var in used_vars):
                    self.env_list.append(f'\t\t{self.deployment_name.upper()}_{sprite.__name__.upper()}_{var.upper()}={val}')
                used_vars.append(var)
                
            self.env_list.append('\n\t\t# Optional #')
            for service in services:
                for var, val in vars(service).items():
                    if not (var.startswith('_') or callable(getattr(service, var)) or var in used_vars):
                        self.env_list.append(f'\t\t{self.deployment_name.upper()}_{sprite.__name__.upper()}_{var.upper()}={val}')
                used_vars.append(var)
                
    def iterate_sprites_moniker_level(self, sprites, services, moniker):
        for sprite in sprites:
            used_vars = []
            self.env_list.append(f'\n\t## {sprite.__name__.upper()} Variables ##\n')
            self.env_list.append('\t\t# Required here or at deployment level #')
            for var in sprite._SECRET_VARIABLES:
                self.env_list.append(f'\t\t{self.deployment_name.upper()}_{sprite.__name__.upper()}_{var.upper()}=')
                used_vars.append(var)
                
            self.env_list.append('\n\t\t# Required here or at deployment level or at moniker level #')
            for service in services:
                for var in service._SECRET_VARIABLES:
                    self.env_list.append(f'\t\t{self.deployment_name.upper()}_{moniker.upper()}_{sprite.__name__.upper()}_{var.upper()}=')
                    used_vars.append(var)
                    
            self.env_list.append('\n\t\t# Recommended #')
            for var, val in vars(sprite).items():
                if not (var.startswith('_') or callable(getattr(sprite, var)) or var in used_vars):
                    self.env_list.append(f'\t\t{self.deployment_name.upper()}_{moniker.upper()}_{sprite.__name__.upper()}_{var.upper()}={val}')
                used_vars.append(var)
                
            self.env_list.append('\n\t\t# Optional #')
            for service in services:
                for var, val in vars(service).items():
                    if not (var.startswith('_') or callable(getattr(service, var)) or var in used_vars):
                        self.env_list.append(f'\t\t{self.deployment_name.upper()}_{moniker.upper()}_{sprite.__name__.upper()}_{var.upper()}={val}')
                used_vars.append(var)
