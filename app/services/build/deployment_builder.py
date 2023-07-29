import os
import textwrap
import traceback
import yaml
from ruamel.yaml import YAML
from services.classes.deployment_runner import DeploymentClass, MonikerClass
from services.classes.base import BaseClass
from services.classes.config import DiscordConfig, ShelbyConfig

class ConfigTemplateCreator(DeploymentClass):
    def __init__(self, deployment_name):
        self.deployment_name = deployment_name

    def create_template(self):
        yaml = YAML()
        with open("deployments/template/template_config.yaml", "r", encoding="utf-8") as file:
            data = yaml.load(file)

        # Modify the variable
        data[
            "deployment_name"
        ] = (
            self.deployment_name
        )  # replace 'your_variable' with the actual variable you want to change

        # Write the modified data to a new file
        with open("output.yaml", "w", encoding="utf-8") as file:
            yaml.dump(data, file)

        dir_path = f"deployments/{self.deployment_name}"
        file_path = f"{dir_path}/{self.deployment_name}_deployment_config.yaml"

        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        yaml.indent(mapping=2, sequence=4, offset=2)
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as outfile:
                yaml.dump(data, outfile)
        else:
            raise FileExistsError(f"The file {file_path} already exists.")

class EnvConfigCreator(DeploymentClass):
    
    def __init__(self, deployment_name):
        self.deployment_name = deployment_name
        # Get deployment.env
        self.dir_path = f"deployments/{self.deployment_name}"
        self.file_path = f"{self.dir_path}/{self.deployment_name}_deployment.env"
        if os.path.exists(self.file_path):
            self.existing_env_vars = self.load_existing_env_file(self.file_path)
        else:
            self.existing_env_vars = None
        with open(
            f"deployments/{self.deployment_name}/{self.deployment_name}_deployment_config.yaml",
            "r", encoding="utf-8"
            ) as infile:
            self.config_file = yaml.safe_load(infile)
            
        self.all_sprites = [DiscordConfig]
        self.all_services = [ShelbyConfig]
        
        self.enabled_moniker_names = self.load_moniker_names(self.config_file)
        self.env_list = []

    def update_config(self):
        
        # Line are appended to env_list which is then used to generate file.
        self.generate_devops_level()
        self.iterate_deployment_class()
        
        for moniker in self.enabled_moniker_names:
            self.generate_moniker_level(moniker)
            
        env_string = "\n".join(self.env_list)
        env_string = textwrap.indent(env_string, " " * 24)
        local_env_file = textwrap.dedent(
            f"""\
{env_string}
        """
        )
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write(local_env_file)

    def load_moniker_names(self, config_file):
        enabled_moniker_names = [moniker['moniker_name'] for moniker in config_file['monikers']]
        return enabled_moniker_names
    
    def generate_devops_level(self):  
        self.env_list.append("\t## Devops variables only set at deployment level ##\n")
        self.env_list.append("\t\t# These are required to deploy to container #")
        self.env_list.append(f"\t\tDEPLOYMENT_NAME={self.deployment_name}")
        for var in DeploymentClass.DEVOPS_VARIABLES_:
            env_var_name = f"{self.deployment_name}_{var}"
            check_env = self.only_add_env_vars(env_var_name)
            self.env_list.append(f"\t\t{check_env}")

    def iterate_deployment_class(self):
        used_vars = []
        self.env_list.append("\n### Deployment level Variables ###\n")
        self.env_list.append("\t\t# Required here #")
        for var in DeploymentClass.DEPLOYMENT_REQUIRED_VARIABLES_:
            env_var_name = f"{self.deployment_name}_{var}"
            check_env = self.only_add_env_vars(env_var_name)
            self.env_list.append(f"\t\t{check_env}")
        for sprite in self.all_sprites:
            for var in sprite.DEPLOYMENT_REQUIRED_VARIABLES_:
                if var not in used_vars:
                    env_var_name = f"{self.deployment_name}_{var}"
                    check_env = self.only_add_env_vars(env_var_name)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
                    
        for service in self.all_services:
            for var in service.DEPLOYMENT_REQUIRED_VARIABLES_:
                if var not in used_vars:
                    env_var_name = f"{self.deployment_name}_{var}"
                    check_env = self.only_add_env_vars(env_var_name)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
                    
        self.env_list.append("\n\t\t# Recommended #")
        for sprite in self.all_sprites:
            for var, val in vars(sprite).items():
                if not (
                    var.startswith("_")
                    or var.endswith("_")
                    or callable(getattr(sprite, var))
                    or var in used_vars
                ):
                    env_var_name = f"{self.deployment_name}_{sprite.__name__}_{var}"
                    check_env = self.add_env_or_class_vars(env_var_name, val)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
                
        self.env_list.append("\n\t\t# Optional #")
        for sprite in self.all_sprites:
            for var in sprite.SPRITE_REQS_:
                for class_name in sprite.SPRITE_REQS_:
                    service = self.CLASSES_[class_name]
                    for var, val in vars(service).items():
                        if not (
                            var.startswith("_")
                            or var.endswith("_")
                            or callable(getattr(service, var))
                            or var in used_vars
                        ):
                            env_var_name = f"{self.deployment_name}_{sprite.__name__}_{var}"
                            check_env = self.add_env_or_class_vars(env_var_name, val)
                            self.env_list.append(f"\t\t{check_env}")
                            used_vars.append(var)
        
    def generate_moniker_level(self, moniker_name):
        used_vars = []
        self.env_list.append(
            f"\n### {moniker_name.upper()} Level Variables ###\n"
        )
        self.env_list.append("\t\t# Required here #")
        for var in MonikerClass.MONIKER_REQUIRED_VARIABLES_:
            env_var_name = f"{self.deployment_name}_{moniker_name}_{var}"
            check_env = self.only_add_env_vars(env_var_name)
            self.env_list.append(f"\t\t{check_env}")
        for sprite in self.all_sprites:
            for var in sprite.MONIKER_REQUIRED_VARIABLES_:
                if var not in used_vars:
                    env_var_name = f"{self.deployment_name}_{moniker_name}_{sprite.__name__}_{var}"
                    check_env = self.only_add_env_vars(env_var_name)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
                    
        for service in self.all_services:
            for var in service.MONIKER_REQUIRED_VARIABLES_:
                if var not in used_vars:
                    env_var_name = f"{self.deployment_name}_{moniker_name}_{service.__name__}_{var}"
                    check_env = self.only_add_env_vars(env_var_name)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
                    
        self.env_list.append("\n\t\t# Optional - Overrides deployment level variables #")
        for sprite in self.all_sprites:
            for var, _ in vars(sprite).items():
                if not (
                    var.startswith("_")
                    or var.endswith("_")
                    or callable(getattr(sprite, var))
                    or var in used_vars
                ):
                    env_var_name = f"{self.deployment_name}_{moniker_name}_{sprite.__name__}_{var}"
                    check_env = self.only_add_env_vars(env_var_name)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
        
        for sprite in self.all_sprites:
            for var in sprite.SPRITE_REQS_:
                for class_name in sprite.SPRITE_REQS_:
                    service = self.CLASSES_[class_name]
                    for var, _ in vars(service).items():
                        if not (
                            var.startswith("_")
                            or var.endswith("_")
                            or callable(getattr(service, var))
                            or var in used_vars
                        ):
                            env_var_name = f"{self.deployment_name}_{moniker_name}_{sprite.__name__}_{var}"
                            check_env = self.only_add_env_vars(env_var_name)
                            self.env_list.append(f"\t\t{check_env}")
                            used_vars.append(var)
                  
    def add_env_or_class_vars(self, env_var_name, val):
        if self.existing_env_vars:
            env_var_name = env_var_name.upper()
            env_val = self.existing_env_vars.get(env_var_name, "")
            if env_val is str:
                env_val = env_val.strip()
            if env_val != "" and env_val != "None":
                return f"{env_var_name}={env_val}"
        if val is not None:
            return f"{env_var_name}={val}"
        return f"{env_var_name}="

    def only_add_env_vars(self, env_var_name):
        # Only add vars if they already existed in the deployment.env
        if self.existing_env_vars:
            env_var_name = env_var_name.upper()
            env_val = self.existing_env_vars.get(env_var_name, "")
            if env_val is str:
                env_val = env_val.strip()
            if env_val != "" and env_val != "None":
                return f"{env_var_name}={env_val}"
        return f"{env_var_name}="

class WorkflowBuilder(DeploymentClass):
    def __init__(self, deployment_name):
        ConfigCreator(deployment_name).update_config()

        self.deployment_name = deployment_name
        self.dir_path = f"deployments/{self.deployment_name}"
        self.file_path = f"{self.dir_path}/{self.deployment_name}_deployment.env"
        self.env_list = []
        self.secrets_list = []

        try:
            self.env_vars_file = self.load_existing_env_file(self.file_path)
            with open(
                f"deployments/{self.deployment_name}/{self.deployment_name}_deployment_config.yaml",
                "r",
            ) as infile:
                self.config_file = yaml.safe_load(infile)
        except Exception as error:
            print(f"Error: requires deployment.env and deployment_config.yaml {error}")
            raise

        self.sprites = set()
        self.sprite_names = set()
        self.moniker_names = set()
        for moniker in self.config_file["monikers"]:
            self.moniker_names.add(moniker["name"])
            for sprite_name, sprite_value in moniker["sprites"].items():
                if sprite_value is True:
                    match sprite_name:
                        case "discord":
                            sprite = DiscordSprite
                        case "web":
                            sprite = WebSprite
                        case "slack":
                            sprite = SlackSprite
                        case _:
                            continue
                    self.sprites.add(sprite)
                    self.sprite_names.add(sprite_name)

        self.deployment_env = DeploymentServicesRequiredEnvs(self.deployment_settings)
        self.deployment_name = self.deployment_settings["deployment_name"]

    def build_workflow(self):
        self.generate_dockerfile()
        self.generate_pip_requirements()
        self.populate_variables()
        self.generate_actions_workflow()
        # self.generate_local_env_file(self.local_env_list, local_secrets_list)

        # self.docker_server: str = f'{self.docker_registry}/{self.docker_username}/{self.docker_repo}'
        # self.docker_image_path: str = f'{self.docker_username}/{self.docker_repo}:{deployment_settings["deployment_name"]}-latest'
        # self.github_action_workflow_name: str = f'deploy-{deployment_settings["deployment_name"]}'
        # self.workload_name: str = f'{deployment_settings["deployment_name"]}-workload'
        # self.workload_slug: str = f'{deployment_settings["deployment_name"]}-slug'

    def load_existing_env_file(self, filepath):
        env_vars = {}
        with open(filepath, "r") as f:
            for line in f:
                try:
                    key, value = line.strip().split("=", 1)
                    env_vars[key] = value
                except ValueError:
                    # ignore lines that don't contain an equals sign
                    continue
        return env_vars

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
RUN pip install --no-cache-dir -r deployments/{self.deployment_name}/requirements.txt

# Run Sprites
CMD ["/bin/bash", "-c", "python app/run.py --deployment {self.deployment_name}"]
        """
        with open(f"deployments/{self.deployment_name}//Dockerfile", "w") as f:
            f.write(dockerfile)

    def generate_pip_requirements(self):
        combined_requirements = set()
        for sprite_name in self.sprite_names:
            with open(f"app/services/deployment{sprite_name}_requirements.txt") as file:
                sprite_requirements = set(file.read().splitlines())
            combined_requirements.update(sprite_requirements)

        with open(
            f"deployments/{self.deployment_name}/requirements.txt", "w"
        ) as file:
            file.write("\n".join(combined_requirements))

    def populate_variables(self):
        self.env_list = []
        self.local_env_list = []
        self.generate_default_secrets()
        # For Each Moniker
        for moniker in self.config_file["monikers"]:
            self.env_list.append(f'\n### {moniker["name"]}_environment_variables ###\n')
            # For each Sprite
            for sprite_name, sprite_value in moniker["sprites"].items():
                if sprite_value is True:
                    match sprite_name:
                        case "discord":
                            self.secrets_list.append(
                                f"""{moniker["name"].upper()}_DISCORD_SPRITE_BOT_TOKEN: ${{{{ secrets.{moniker["name"].upper()}_DISCORD_SPRITE_BOT_TOKEN }}}}"""
                            )

                            discord_config = DiscordSpriteConfig()
                            discord_config.create_discord_deployment(
                                moniker["name"], sprite_config
                            )

                            for field_name in vars(discord_config):
                                value = getattr(discord_config, field_name)
                                if value is not None:
                                    self.env_list.append(
                                        f"""{moniker["name"].upper()}_{platform.upper()}_{field_name.upper()}: {value}"""
                                    )

                        case "slack":
                            self.secrets_list.append(
                                f"""{moniker["name"].upper()}_SLACK_BOT_TOKEN: ${{{{ secrets.{moniker["name"].upper()}_SLACK_SPRITE_BOT_TOKEN }}}}"""
                            )

                            self.secrets_list.append(
                                f"""{moniker["name"].upper()}_SLACK_APP_TOKEN: ${{{{ secrets.{moniker["name"].upper()}_SLACK_SPRITE_APP_TOKEN }}}}"""
                            )

                        case _:
                            continue

        self.env_list.append("\n### deployment_services_environment_variables ###\n")

        for field_name in vars(self.deployment_env):
            value = getattr(self.deployment_env, field_name)
            if value is not None:
                self.env_list.append(f"""{field_name.upper()}: {value}""")

        self.env_list.append("\n### config_overrides_variables ###\n")

        for override_name, override_value in self.deployment_settings[
            "config_overrides"
        ].items():
            self.env_list.append(f"""{override_name.upper()}: {override_value}""")

    def generate_default_secrets(self):
        self.secrets_list = []

        secret_names = [
            "STACKPATH_CLIENT_ID",
            "STACKPATH_API_CLIENT_SECRET",
            "OPENAI_API_KEY",
            "PINECONE_API_KEY",
            "DOCKER_TOKEN",
        ]
        for secret in secret_names:
            self.secrets_list.append(
                f"""{secret.upper()}: ${{{{ secrets.{secret.upper()} }}}}"""
            )

    def generate_actions_workflow(self):
        # Positioning is required to create correct formatting. Hack work.
        secrets_string = "\n".join(self.secrets_list)
        secrets_string = textwrap.indent(secrets_string, " " * 24)

        env_string = "\n".join(self.env_list)
        env_string = textwrap.indent(env_string, " " * 24)

        github_actions_script = textwrap.dedent(
            f"""\
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
        """
        )

        github_actions_script = github_actions_script.replace("    ", "  ")
        os.makedirs(".github/workflows", exist_ok=True)
        # with open(f'.github/workflows/{deployment_settings.github_action_workflow_name}.yaml', 'w') as f:
        with open(
            f".github/workflows/{self.deployment_name}_deployment.yaml", "w"
        ) as f:
            f.write(github_actions_script)
