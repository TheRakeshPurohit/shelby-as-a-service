import os
import textwrap
import yaml
from ruamel.yaml import YAML
import traceback
from services.shelby_agent import ShelbyAgent
from sprites.discord_sprite import DiscordSprite
from services.base_class import BaseClass

class ConfigTemplate(BaseClass):
    
    def __init__(self, new_deployment_name):
        self.deployment_name = new_deployment_name
    
    def create_template(self):
        
        yaml = YAML()
        with open('app/deployments/template/template_config.yaml', 'r') as file:
            data = yaml.load(file)
        
        # Modify the variable
        data['deployment_name'] = self.deployment_name  # replace 'your_variable' with the actual variable you want to change

        # Write the modified data to a new file
        with open('output.yaml', 'w') as file:
            yaml.dump(data, file)
            
        dir_path = f'app/deployments/{self.deployment_name}'
        file_path = f'{dir_path}/{self.deployment_name}_deployment_config.yaml'

        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            
        yaml.indent(mapping=2, sequence=4, offset=2)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as outfile:
                yaml.dump(data, outfile)
        else:
            raise FileExistsError(f"The file {file_path} already exists.")

class ConfigCreator(BaseClass):
    
    def __init__(self, new_deployment_name):
        
        self.deployment_name = new_deployment_name
        self.dir_path = f'app/deployments/{self.deployment_name}'
        self.file_path = f'{self.dir_path}/{self.deployment_name}_deployment.env'
        if os.path.exists(self.file_path):
                self.existing_env_vars = self.load_existing_env_variables(self.file_path)
        else:
            self.existing_env_vars = None
        if not os.path.exists(self.dir_path):
            os.makedirs(self.dir_path)
        with open(f'app/deployments/{self.deployment_name}/{self.deployment_name}_deployment_config.yaml', 'r') as infile:
                self.config_file = yaml.safe_load(infile)
        
    def update_config(self):
        services = set([ShelbyAgent])
        try:
            self.env_list = []
            self.iterate_base_class()
            
            sprites = set()
            for moniker in self.config_file['monikers']:
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
            self.iterate_sprites_deployment_level(sprites, services)
            
            for moniker in self.config_file['monikers']:
                moniker_name = moniker['name']
                self.env_list.append(f'\n### {moniker_name.upper()} Level Variables ###\n')
                self.env_list.append('\t\t# Required here #')
                self.env_list.append(f'\t\t{self.deployment_name.upper()}_{moniker_name.upper()}_ENABLED={moniker["enabled"]}')
                self.env_list.append(f'\t\t{self.deployment_name.upper()}_{moniker_name.upper()}_ENABLED_DATA_NAMESPACES={",".join(moniker["enabled_data_namespaces"])}')
                self.env_list.append('\n\t\t# Required here or at deployment level or in sprite variables #')
                class_vars = [var for var in vars(BaseClass) if not var in BaseClass._DEVOPS_VARIABLES]
                for var in class_vars:
                    if not (var.startswith('_') or callable(getattr(BaseClass, var))):
                        check_env = self.check_existing(f'{self.deployment_name.upper()}_{moniker_name.upper()}_{var.upper()}')
                        self.env_list.append(f'\t\t{check_env}')
                for sprite_name, sprite_value in moniker['sprites'].items():
                    if sprite_value is True:
                        match sprite_name:
                            case 'discord':
                                self.iterate_sprites_moniker_level(DiscordSprite, services, moniker)
                            # case 'web':
                            #     self.iterate_sprites_moniker_level(WebSprite, services, moniker_name)
                            # case 'slack':
                            #     self.iterate_sprites_moniker_level(SlackSprite, services, moniker_name)
                            case _:
                                continue

            self.env_list.append(f'\nDEPLOYMENT_POPULATED=False')
            env_string = '\n'.join(self.env_list)
            env_string = textwrap.indent(env_string, ' ' * 24)
            local_env_file = textwrap.dedent(f"""\
{env_string}
            """)

            with open(self.file_path, 'w') as f:
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
            check_env = self.check_existing(f'{self.deployment_name.upper()}_{var.upper()}')
            self.env_list.append(f'\t\t{check_env}')
            used_vars.append(var)
        self.env_list.append('\n### Deployment level Variables ###\n')
        self.env_list.append('\t\t# Required here or in sprite variables #')
        for var, val in vars(BaseClass).items() :
            if not (var.startswith('_') or callable(getattr(BaseClass, var)) or var in used_vars):
                check_env = self.check_existing(f'{self.deployment_name.upper()}_{var.upper()}', val)
                self.env_list.append(f'\t\t{check_env}')
                     
    def iterate_sprites_deployment_level(self, sprites, services):
        for sprite in sprites:
            used_vars = []
            self.env_list.append(f'\n\t## {sprite.__name__.upper()} Variables ##\n')
            self.env_list.append('\t\t# Required here #')
            for var in sprite._SECRET_VARIABLES:
                check_env = self.check_existing(f'{self.deployment_name.upper()}_{sprite.__name__.upper()}_{var.upper()}')
                self.env_list.append(f'\t\t{check_env}')
                used_vars.append(var)
                
            self.env_list.append('\n\t\t# Required here or at deployment level #')
            for service in services:
                for var in service._SECRET_VARIABLES:
                    check_env = self.check_existing(f'{self.deployment_name.upper()}_{sprite.__name__.upper()}_{var.upper()}')
                    self.env_list.append(f'\t\t{check_env}')
                    used_vars.append(var)
                    
            self.env_list.append('\n\t\t# Recommended #')
            for var, val in vars(sprite).items():
                if not (var.startswith('_') or callable(getattr(sprite, var)) or var in used_vars):
                    check_env = self.check_existing(f'{self.deployment_name.upper()}_{sprite.__name__.upper()}_{var.upper()}', val)
                    self.env_list.append(f'\t\t{check_env}')
                    used_vars.append(var)
                
            self.env_list.append('\n\t\t# Optional #')
            for service in services:
                for var, val in vars(service).items():
                    if not (var.startswith('_') or callable(getattr(service, var)) or var in used_vars):
                        check_env = self.check_existing(f'{self.deployment_name.upper()}_{sprite.__name__.upper()}_{var.upper()}', val)
                        self.env_list.append(f'\t\t{check_env}')
                        used_vars.append(var)
                
    def iterate_sprites_moniker_level(self, sprite, services, moniker):
        moniker_name = moniker['name']
        used_vars = []
        self.env_list.append(f'\n\t## {sprite.__name__.upper()} Variables ##\n')
        
        # I don't think we want multiple bots.
        # self.env_list.append('\t\t# Required here or at deployment level #')
        # for var in sprite._SECRET_VARIABLES:
        #     check_env = self.check_existing(f'{self.deployment_name.upper()}_{moniker_name.upper()}_{sprite.__name__.upper()}_{var.upper()}')
        #     self.env_list.append(f'\t\t{check_env}')
        #     used_vars.append(var)
            
        self.env_list.append('\t\t# Required here or at deployment level or at moniker level #')
        for service in services:
            for var in service._SECRET_VARIABLES:
                check_env = self.check_existing(f'{self.deployment_name.upper()}_{moniker_name.upper()}_{sprite.__name__.upper()}_{var.upper()}')
                self.env_list.append(f'\t\t{check_env}')
                used_vars.append(var)
                
        self.env_list.append('\n\t\t# Recommended #')
        for var, val in vars(sprite).items():
            if not (var.startswith('_') or callable(getattr(sprite, var)) or var in used_vars):
                check_env = self.check_existing(f'{self.deployment_name.upper()}_{moniker_name.upper()}_{sprite.__name__.upper()}_{var.upper()}', val)
                self.env_list.append(f'\t\t{check_env}')
                used_vars.append(var)
            
        self.env_list.append('\n\t\t# Optional #')
        for service in services:
            for var, val in vars(service).items():
                if not (var.startswith('_') or callable(getattr(service, var)) or var in used_vars):
                    check_env = self.check_existing(f'{self.deployment_name.upper()}_{moniker_name.upper()}_{sprite.__name__.upper()}_{var.upper()}', val)
                    self.env_list.append(f'\t\t{check_env}')
                    used_vars.append(var)

    def load_existing_env_variables(self, filepath):
        env_vars = {}
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    key, value = line.strip().split('=', 1)
                    env_vars[key] = value
                except ValueError:
                    # ignore lines that don't contain an equals sign
                    continue
        return env_vars

    def check_existing(self, var, val=None):
        if self.existing_env_vars:
            env_var = self.existing_env_vars.get(var, "")
            # An empty string evaluates to false. I hate python.
            if env_var.strip() or env_var != 'None':
                return f'{var}={env_var}'
        if val is None:
            return f'{var}='
        return f'{var}={val}'
 
# class WorkflowCreator(BaseClass):
    
#     def __init__(self, deployment_settings_filename, log_service):
#         self.log_service = log_service
#         with open(deployment_settings_filename, 'r') as stream:
#                 self.deployment_settings = yaml.safe_load(stream)
#         self.deployment_env = DeploymentServicesRequiredEnvs(self.deployment_settings, self.log_service)
#         self.deployment_name = self.deployment_settings["deployment_name"]
        
#     def create_deployment_from_file(self):
        
#         self.generate_dockerfile()
#         self.generate_shell_script()
#         self.generate_pip_requirements()
#         deploy_env_list, local_env_list, deploy_secrets_list, local_secrets_list = self.populate_variables()
#         self.generate_actions_workflow(deploy_env_list , deploy_secrets_list)
#         # self.generate_local_env_file(local_env_list, local_secrets_list)
        
#         # self.docker_server: str = f'{self.docker_registry}/{self.docker_username}/{self.docker_repo}'
#         # self.docker_image_path: str = f'{self.docker_username}/{self.docker_repo}:{deployment_settings["deployment_name"]}-latest'
#         # self.github_action_workflow_name: str = f'deploy-{deployment_settings["deployment_name"]}'
#         # self.workload_name: str = f'{deployment_settings["deployment_name"]}-workload'
#         # self.workload_slug: str = f'{deployment_settings["deployment_name"]}-slug'
        
#     def generate_dockerfile(self):
        

#         dockerfile = f"""\
# # Use an official Python runtime as a parent image
# FROM python:3-slim-buster

# # Install Git
# RUN apt-get update && apt-get install -y git

# # Set the working directory in the container to /shelby-as-a-service
# WORKDIR /shelby-as-a-service

# # Copy all files and folders from the root directory
# COPY ./ ./ 

# # Install python packages
# RUN pip install --no-cache-dir -r app/deploy/automation/{self.deployment_name}/requirements.txt

# # Run Sprites
# CMD ["/bin/bash", "app/deploy/automation/{self.deployment_name}/startup.sh"]
#         """

#         os.makedirs(f'app/deploy/automation/{self.deployment_name}', exist_ok=True)
#         with open(f'app/deploy/automation/{self.deployment_name}/Dockerfile', 'w') as f:
#             f.write(dockerfile)

#     def generate_shell_script(self):
#         scripts_string = ''
#         for moniker, moniker_config in self.deployment_settings["monikers"].items():
#             for sprite in moniker_config["sprites"]:
#                 scripts_string += f'python app/run.py --deployment {self.deployment_name} {moniker} {sprite} &\n'

#         script_content = f"""\
# #!/bin/bash
# # start_up.sh

# # Start scripts in background
# {scripts_string}

# # Wait for all background processes to finish
# wait
# """

#         os.makedirs(f'app/deploy/automation/{self.deployment_name}', exist_ok=True)
#         with open(f'app/deploy/automation/{self.deployment_name}/startup.sh', 'w') as f:
#             f.write(script_content)

#     def generate_pip_requirements(self):
#         self.unique_platforms = {sprite for moniker_config in self.deployment_settings["monikers"].values() for sprite in moniker_config["sprites"].keys()}

#         combined_requirements = set()

#         for platform in self.unique_platforms:
#             with open(f'app/deploy/automation/{platform}_requirements.txt') as file:
#                 platform_requirements = set(file.read().splitlines())
#             combined_requirements.update(platform_requirements)

#         os.makedirs(f'app/deploy/automation/{self.deployment_name}', exist_ok=True)
#         with open(f'app/deploy/automation/{self.deployment_name}/requirements.txt', 'w') as file:
#             file.write('\n'.join(combined_requirements))

#     def generate_actions_workflow(self, deploy_env_list , deploy_secrets_list):
    
#         # Positioning is required to create correct formatting. Hack work.
#         secrets_string = '\n'.join(deploy_secrets_list)
#         secrets_string = textwrap.indent(secrets_string, ' ' * 24)

#         env_string = '\n'.join(deploy_env_list )
#         env_string = textwrap.indent(env_string, ' ' * 24)
                
#         github_actions_script = textwrap.dedent(f"""\
#         name: {self.deployment_env.github_action_workflow_name}

#         on: workflow_dispatch

#         jobs:
#             docker:
#                 runs-on: ubuntu-latest
#                 env:
#                         ### Secrets ###
#                         # Secrets in the format of 'secrets.NAME'
#                         # Should be added be added to github secrets as 'NAME'
#                     \n{secrets_string}
#                     \n{env_string}
                    
#                 steps:
#                     - name: Checkout code
#                         uses: actions/checkout@v3
                                        
#                     - name: Set up Python
#                         uses: actions/setup-python@v2
#                         with:
#                             python-version: '3.10.11'

#                     - name: Cache pip dependencies
#                         uses: actions/cache@v2
#                         id: cache
#                         with:
#                             path: ~/.cache/pip 
#                             key: ${{{{  runner.os }}}}-pip-${{{{  hashFiles('**app/deploy/automation/{self.deployment_name}/requirements.txt') }}}}
#                             restore-keys: |
#                                 ${{{{  runner.os }}}}-pip-

#                     - name: Install dependencies
#                         run: |
#                             python -m pip install --upgrade pip
#                             if [ -f app/deploy/automation/{self.deployment_name}/requirements.txt ]; then pip install -r app/deploy/automation/{self.deployment_name}/requirements.txt; fi

#                     - name: Login to Docker registry
#                         uses: docker/login-action@v2 
#                         with:
#                             registry: {self.deployment_env.docker_registry}
#                             username: {self.deployment_env.docker_username}
#                             password: ${{{{  secrets.DOCKER_TOKEN }}}}

#                     - name: Build and push Docker image
#                         uses: docker/build-push-action@v4
#                         with:
#                             context: .
#                             file: app/deployment/{self.deployment_name}/Dockerfile
#                             push: true
#                             tags: {self.deployment_env.docker_image_path}

#                     - name: Add execute permissions to the script
#                         run: chmod +x app/deploy/automation/deploy_stackpath_container.py

#                     - name: Run deployment script
#                         run: app/deploy/automation/deploy_stackpath_container.py
#         """)
        
#         github_actions_script = github_actions_script.replace('    ', '  ')
#         os.makedirs('.github/workflows', exist_ok=True)
#         # with open(f'.github/workflows/{deployment_settings.github_action_workflow_name}.yaml', 'w') as f:
#         with open(f'.github/workflows/{self.deployment_name}_deployment.yaml', 'w') as f:
#             f.write(github_actions_script)
                      
#     def populate_variables(self):
        
#         deploy_env_list = []
#         local_env_list = []
#         deploy_secrets_list, local_secrets_list = self.generate_default_secrets()
#         # For Each Moniker
#         for moniker_name, moniker_config in self.deployment_settings["monikers"].items():
#             deploy_env_list.append(f'\n### {moniker_name}_environment_variables ###\n')
#             local_env_list.append(f'\n### {moniker_name}_environment_variables ###\n')
#             # For each Sprite
#             for platform, sprite_config in moniker_config["sprites"].items():
#                 match platform:
#                     case 'discord':
#                         deploy_secrets_list.append(f"""{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN: ${{{{ secrets.{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN }}}}""")
#                         local_secrets_list.append(f"""{moniker_name.upper()}_DISCORD_SPRITE_BOT_TOKEN=""")
#                         discord_config = DiscordSpriteConfig()
#                         discord_config.create_discord_deployment(moniker_name, sprite_config, self.log_service)

#                         for field_name in vars(discord_config):
#                             value = getattr(discord_config, field_name)
#                             if value is not None:
#                                 deploy_env_list.append(f"""{moniker_name.upper()}_{platform.upper()}_{field_name.upper()}: {value}""")
#                                 local_env_list.append(f"""{moniker_name.upper()}_{platform.upper()}_{field_name.upper()}={value}""")
                                
#                     case 'slack':
#                         deploy_secrets_list.append(f"""{moniker_name.upper()}_SLACK_BOT_TOKEN: ${{{{ secrets.{moniker_name.upper()}_SLACK_SPRITE_BOT_TOKEN }}}}""")
#                         local_secrets_list.append(f"""{moniker_name.upper()}_SLACK_BOT_TOKEN=""")
#                         deploy_secrets_list.append(f"""{moniker_name.upper()}_SLACK_APP_TOKEN: ${{{{ secrets.{moniker_name.upper()}_SLACK_SPRITE_APP_TOKEN }}}}""")
#                         local_secrets_list.append(f"""{moniker_name.upper()}_SLACK_APP_TOKEN=""")
                        
#         deploy_env_list.append('\n### deployment_services_environment_variables ###\n')
#         local_env_list.append('\n### deployment_services_environment_variables ###\n')
#         for field_name in vars(self.deployment_env):
#             value = getattr(self.deployment_env, field_name)
#             if value is not None:
#                 deploy_env_list.append(f"""{field_name.upper()}: {value}""")
#                 local_env_list.append(f"""{field_name.upper()}={value}""")
        
#         deploy_env_list.append('\n### config_overrides_variables ###\n')
#         local_env_list.append('\n### config_overrides_variables ###\n')
#         for override_name, override_value in self.deployment_settings["config_overrides"].items():
#             deploy_env_list.append(f"""{override_name.upper()}: {override_value}""")
#             local_env_list.append(f"""{override_name.upper()}={override_value}""")
    
#         return deploy_env_list, local_env_list, deploy_secrets_list, local_secrets_list
    
#     def generate_default_secrets(self):
#         deploy_secrets_list = []
#         local_secrets_list = []
#         secret_names = ['STACKPATH_CLIENT_ID', 'STACKPATH_API_CLIENT_SECRET', 'OPENAI_API_KEY', 'PINECONE_API_KEY', 'DOCKER_TOKEN']
#         for secret in secret_names:
#             deploy_secrets_list.append(f"""{secret.upper()}: ${{{{ secrets.{secret.upper()} }}}}""")
#             local_secrets_list.append(f"""{secret.upper()}=""")
        
#         return deploy_secrets_list, local_secrets_list
    