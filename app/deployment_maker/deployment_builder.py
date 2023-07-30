import os
import textwrap
import traceback
import yaml
import json
from ruamel.yaml import YAML
from deployment_configurator.deployment_instance import DeploymentInstance, MonikerInstance
from deployment_configurator.shared_tools import ConfigSharedTools 
from deployment_configurator.data_classes import AllSpritesAndServices, DiscordConfig, ShelbyConfig

class ConfigTemplateCreator(DeploymentInstance):
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

class EnvConfigCreator(DeploymentInstance):
    
    def __init__(self, deployment_name):
        self.deployment_name = deployment_name
        # Get deployment.env
        self.dir_path = f"deployments/{self.deployment_name}"
        self.file_path = f"{self.dir_path}/{self.deployment_name}_deployment.env"
        if os.path.exists(self.file_path):
            self.existing_env_vars = ConfigSharedTools.load_existing_env_file(self.file_path)
        else:
            self.existing_env_vars = None
        with open(
            f"deployments/{self.deployment_name}/{self.deployment_name}_deployment_config.yaml",
            "r", encoding="utf-8"
            ) as infile:
            self.config_file = yaml.safe_load(infile)
            
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
        for var in DeploymentInstance.DEVOPS_VARIABLES_:
            env_var_name = f"{self.deployment_name}_{var}"
            check_env = self.only_add_env_vars(env_var_name)
            self.env_list.append(f"\t\t{check_env}")

    def iterate_deployment_class(self):
        used_vars = []
        self.env_list.append("\n### Deployment Level Variables ###\n")
        self.env_list.append("\t\t# User input required here #")
        for var in DeploymentInstance.DEPLOYMENT_REQUIRED_VARIABLES_:
            env_var_name = f"{self.deployment_name}_{var}"
            check_env = self.only_add_env_vars(env_var_name)
            self.env_list.append(f"\t\t{check_env}")
        for sprite in AllSpritesAndServices.all_sprites:
            for var in sprite.DEPLOYMENT_REQUIRED_VARIABLES_:
                if var not in used_vars:
                    env_var_name = f"{self.deployment_name}_{var}"
                    check_env = self.only_add_env_vars(env_var_name)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
                    
        for service in AllSpritesAndServices.all_services:
            for var in service.DEPLOYMENT_REQUIRED_VARIABLES_:
                if var not in used_vars:
                    env_var_name = f"{self.deployment_name}_{var}"
                    check_env = self.only_add_env_vars(env_var_name)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
                    
        self.env_list.append("\n\t\t# Required default sprite settings - user input recommended #")
        for sprite in AllSpritesAndServices.all_sprites:
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

        self.env_list.append("\n\t\t# Required default service settings - user input optional #")
        for service in AllSpritesAndServices.all_services:
                class_name = service.__name__
                for var, val in vars(service).items():
                    if not (
                        var.startswith("_")
                        or var.endswith("_")
                        or callable(getattr(service, var))
                        or var in used_vars
                    ):
                        env_var_name = f"{self.deployment_name}_{class_name}_{var}"
                        check_env = self.add_env_or_class_vars(env_var_name, val)
                        self.env_list.append(f"\t\t{check_env}")
                
        self.env_list.append("\n\t\t# Optional overrides - overrides defaults for specific sprites #")
        for sprite in AllSpritesAndServices.all_sprites:
            for var in sprite.SPRITE_REQS_:
                for class_name in sprite.SPRITE_REQS_:
                    service = DeploymentInstance.CLASSES_[class_name]
                    for var, _ in vars(service).items():
                        if not (
                            var.startswith("_")
                            or var.endswith("_")
                            or callable(getattr(service, var))
                            or var in used_vars
                        ):
                            env_var_name = f"{self.deployment_name}_{sprite.__name__}_{var}"
                            check_env = self.only_add_env_vars(env_var_name)
                            self.env_list.append(f"\t\t{check_env}")
                        
    def generate_moniker_level(self, moniker_name):
        used_vars = []
        self.env_list.append(
            f"\n### {moniker_name.upper()} Level Variables ###\n"
        )
        self.env_list.append("\t\t# User input required here #")
        for var in MonikerInstance.MONIKER_REQUIRED_VARIABLES_:
            env_var_name = f"{self.deployment_name}_{moniker_name}_{var}"
            check_env = self.only_add_env_vars(env_var_name)
            self.env_list.append(f"\t\t{check_env}")
        for sprite in AllSpritesAndServices.all_sprites:
            for var in sprite.MONIKER_REQUIRED_VARIABLES_:
                if var not in used_vars:
                    env_var_name = f"{self.deployment_name}_{moniker_name}_{sprite.__name__}_{var}"
                    check_env = self.only_add_env_vars(env_var_name)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
                    
        for service in AllSpritesAndServices.all_services:
            for var in service.MONIKER_REQUIRED_VARIABLES_:
                if var not in used_vars:
                    env_var_name = f"{self.deployment_name}_{moniker_name}_{service.__name__}_{var}"
                    check_env = self.only_add_env_vars(env_var_name)
                    self.env_list.append(f"\t\t{check_env}")
                    used_vars.append(var)
                    
        self.env_list.append("\n\t\t# Optional overrides - overrides defaults for specific sprites #")
        for sprite in AllSpritesAndServices.all_sprites:
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
        
            for var in sprite.SPRITE_REQS_:
                for class_name in sprite.SPRITE_REQS_:
                    service = DeploymentInstance.CLASSES_[class_name]
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

class WorkflowBuilder(DeploymentInstance):
    
    def __init__(self, deployment_name):

        self.deployment_name = deployment_name
        self.deployment = DeploymentInstance()
        self.deployment.load_and_check_deployment(deployment_name)
    
        self.secrets_list = []
        self.secrets_to_deploy = []
        self.deployment_vars = {}

        self.dir_path = f"deployments/{self.deployment_name}"
        self.file_path = f"{self.dir_path}/{self.deployment_name}_deployment.env"
        try:
            self.existing_env_vars = ConfigSharedTools.load_existing_env_file(self.file_path)
        except Exception as error:
            print(f"Error: requires deployment.env and deployment_config.yaml {error}")
            raise
        self.enabled_moniker_names = ConfigSharedTools.get_and_convert_env_list(f'{self.deployment_name}_enabled_moniker_names')
        
        self.github_action_workflow_name: str = f'deploy-{self.deployment_name}'
        self.docker_registry: str = None
        self.docker_username: str = None
        self.docker_image_path: str = None
        
        self.docker_repo: str = None

    def build_workflow(self):
        
        self.generate_dockerfile()
        self.generate_pip_requirements()
        self.generate_secrets()
        self.generate_devops_requirements()
        self.get_deployment_requirements()
        self.get_deployment_defaults()
        self.get_monikers()
        
        self.generate_actions_workflow()
    
    def is_secret(self, var):
        if var in DeploymentInstance.SECRET_VARIABLES_:
            return True
        return False
    
    def generate_secrets(self):
        self.secrets_list = []
        for secret in DeploymentInstance.SECRET_VARIABLES_:
            secret_name = f"{self.deployment_name.upper()}_{secret.upper()}"
            self.secrets_to_deploy.append(secret_name)
            self.secrets_list.append(f"{secret_name}:  ${{{{ secrets.{secret_name} }}}}")   
        self.deployment_vars['SECRETS_TO_DEPLOY'] = self.secrets_to_deploy
        
    def generate_devops_requirements(self):  
        self.deployment_vars[f"DEPLOYMENT_NAME"] = self.deployment_name
        for var in DeploymentInstance.DEVOPS_VARIABLES_:
            if self.is_secret(var):
                continue
            env_var_name = f"{self.deployment_name}_{var}"
            env_value = ConfigSharedTools.get_and_convert_env_var(env_var_name)
            self.deployment_vars[f"{var.upper()}"] = f"{env_value}"
            setattr(self, var, env_value)
                    
        # For container deployment
        self.docker_image_path: str = f"{self.docker_username}/{self.docker_repo}:{self.deployment_name}-latest"
        self.deployment_vars[f"DOCKER_IMAGE_PATH"] = self.docker_image_path
        self.deployment_vars[f"DOCKER_USERNAME"] = self.docker_username
        
        
        self.deployment_vars[f"DOCKER_SERVER"] = f"{self.docker_registry}/{self.docker_username}/{self.docker_repo}"
        self.deployment_vars[f"WORKLOAD_NAME"] = f"{self.deployment_name}-workload"
        self.deployment_vars[f"WORKLOAD_SLUG"] = f"{self.deployment_name}-slug"
    
    def get_deployment_requirements(self):
        
        deployment_name = DeploymentInstance.deployment_name
        for var in DeploymentInstance.DEPLOYMENT_REQUIRED_VARIABLES_:
            if self.is_secret(var):
                continue
            env_var_name = f"{deployment_name}_{var}"
            env_value = ConfigSharedTools.get_and_convert_env_var(env_var_name)
            self.deployment_vars[f"{env_var_name.upper()}"] = env_value
        for sprite in DeploymentInstance.used_sprites:
            sprite_classes = []
            sprite_classes.append(sprite)
            if getattr(sprite, 'SPRITE_REQS_', None):
                for class_name in sprite.SPRITE_REQS_:
                    sprite_classes.append(DeploymentInstance.CLASSES_[class_name])
            for ClassConfig in sprite_classes:
                class_config = ClassConfig()
                # Special rules
                for var in class_config.DEPLOYMENT_REQUIRED_VARIABLES_:
                    if self.is_secret(var):
                        continue
                    env_var_name = f"{deployment_name}_{var}"
                    env_value = ConfigSharedTools.get_and_convert_env_var(env_var_name)
                    self.deployment_vars[f"{env_var_name.upper()}"] = env_value
    
    def get_deployment_defaults(self):
        deployment_name = DeploymentInstance.deployment_name
        # Get sprite defaults
        for sprite in DeploymentInstance.used_sprites:
            sprite_name = sprite.__name__
            for var, val in vars(sprite).items():
                if var.startswith("_") or callable(getattr(sprite, var)):
                    continue
                if self.is_secret(var):
                    continue
                deployment_defaults_env_var = f"{deployment_name}_{sprite_name}_{var}"
                deployment_defaults_env_value = ConfigSharedTools.get_and_convert_env_var(deployment_defaults_env_var)
                if deployment_defaults_env_value is not None:
                    self.deployment_vars[f"{deployment_defaults_env_var.upper()}"] = deployment_defaults_env_value
                else:
                    self.deployment_vars[f"{deployment_defaults_env_var.upper()}"] = val
        # Get services defaults
        for service in DeploymentInstance.used_services:
            service_name = service.__name__
            for var, val in vars(service).items():
                if var.startswith("_") or callable(getattr(service, var)):
                    continue
                if self.is_secret(var):
                    continue
                deployment_defaults_env_var = f"{deployment_name}_{service_name}_{var}"
                deployment_defaults_env_value = ConfigSharedTools.get_and_convert_env_var(deployment_defaults_env_var)
                if deployment_defaults_env_value is not None:
                    self.deployment_vars[f"{deployment_defaults_env_var.upper()}"] = deployment_defaults_env_value
                else:
                    self.deployment_vars[f"{deployment_defaults_env_var.upper()}"] = val
        # Get default overrides
        for sprite in DeploymentInstance.used_sprites:
            sprite_name = sprite.__name__
            sprite_classes = []
            if getattr(sprite, 'SPRITE_REQS_', None):
                for class_name in sprite.SPRITE_REQS_:
                    sprite_classes.append(DeploymentInstance.CLASSES_[class_name])
            for ClassConfig in sprite_classes:
                class_config = ClassConfig()
                class_name = class_config.__class__.__name__
                for var, _ in vars(class_config).items():
                    if var.startswith("_") or callable(getattr(class_config, var)):
                        continue
                    if self.is_secret(var):
                        continue
                    deployment_defaults_env_var = f"{deployment_name}_{sprite_name}_{var}"
                    deployment_defaults_env_value = ConfigSharedTools.get_and_convert_env_var(deployment_defaults_env_var)
                    if deployment_defaults_env_value is not None:
                        self.deployment_vars[f"{deployment_defaults_env_var.upper()}"] = deployment_defaults_env_value
    
    def get_monikers(self):
        deployment_name = DeploymentInstance.deployment_name
        for moniker_name, moniker in DeploymentInstance.monikers.items():
            for var in moniker.MONIKER_REQUIRED_VARIABLES_:
                if self.is_secret(var):
                    continue
                env_var_name = f"{deployment_name}_{moniker_name}_{var}"
                env_value = ConfigSharedTools.get_and_convert_env_var(env_var_name)
                self.deployment_vars[f"{env_var_name.upper()}"] = env_value
            for sprite in DeploymentInstance.used_sprites:
                sprite_name = sprite.__name__
                sprite_classes = []
                sprite_classes.append(sprite)
                if getattr(sprite, 'SPRITE_REQS_', None):
                    for class_name in sprite.SPRITE_REQS_:
                        sprite_classes.append(DeploymentInstance.CLASSES_[class_name])
                for ClassConfig in sprite_classes:
                    class_config = ClassConfig()
                    class_name = class_config.__class__.__name__
                    # Special rules
                    for var in class_config.DEPLOYMENT_REQUIRED_VARIABLES_:
                        if self.is_secret(var):
                            continue
                        env_var_name = f"{deployment_name}_{var}"
                        env_value = ConfigSharedTools.get_and_convert_env_var(env_var_name)     
                        self.deployment_vars[f"{env_var_name.upper()}"] = env_value
                    for var in class_config.MONIKER_REQUIRED_VARIABLES_:
                        if self.is_secret(var):
                            continue
                        env_var_name = f"{deployment_name}_{moniker_name}_{class_name}_{var}"
                        env_value = ConfigSharedTools.get_and_convert_env_var(env_var_name)
                        self.deployment_vars[f"{env_var_name.upper()}"] = env_value
                    for var, _ in vars(class_config).items():
                        if var.startswith("_") or callable(getattr(class_config, var)):
                            continue
                        if self.is_secret(var):
                            continue
                        deployment_defaults_env_var = f"{deployment_name}_{moniker_name}_{sprite_name}_{var}"
                        deployment_defaults_env_value = ConfigSharedTools.get_and_convert_env_var(deployment_defaults_env_var)
                        if deployment_defaults_env_value is not None:
                            self.deployment_vars[f"{deployment_defaults_env_var.upper()}"] = deployment_defaults_env_value
    
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

# Run Deployment
CMD ["python", "app/deployment_runner.py", "--container_deployment", "{self.deployment_name}"]
        """
        with open(f"deployments/{self.deployment_name}/Dockerfile", "w", encoding="utf-8") as f:
            f.write(dockerfile)

    def generate_pip_requirements(self):
        combined_requirements = set()
        for sprite_name in AllSpritesAndServices.all_sprites:
            with open(f"app/deployment_maker/{sprite_name.__name__}_requirements.txt", "r", encoding="utf-8") as file:
                sprite_requirements = set(file.read().splitlines())
            combined_requirements.update(sprite_requirements)

        with open(
            f"deployments/{self.deployment_name}/requirements.txt", "w", encoding="utf-8"
        ) as file:
            file.write("\n".join(combined_requirements))

    def populate_strings(self):
        
        # Make sure to error catch any missing # 
        self.deployment_vars.append("\n### ### Secrets ### ###\n")
        self.generate_secrets()
        
        self.deployment_vars.append("\n### Deployment Level Requirements ###\n")
        self.deployment_vars.append("\n### Devops variables only set at deployment level ###\n")
        # iterate_deployment_class
        self.deployment_vars.append("\n### default sprite settings ###\n")
        self.deployment_vars.append("\n### default service settings ###\n")
        self.deployment_vars.append("\n### overrides defaults for specific sprites ###\n")
        # all deployment level are required
        
        self.deployment_vars.append(f"\n### moniker Level Requirements  ###\n")
        # generate_moniker_level
        self.deployment_vars.append(f"\n### overrides defaults for specific spritess ###\n")

    def generate_actions_workflow(self):
        # Positioning is required to create correct formatting. Hack work.
        secret_string = '### Secrets ###\n'
        for secret in self.secrets_list:
            secret_string += f"{secret}\n"
        secret_string += "# Secrets in the format of 'secrets.NAME' with the 'NAME' portion added to your forked repos secrets. #"
        secret_string = textwrap.indent(secret_string, " " * 24)
        env_vars_json = json.dumps(self.deployment_vars)
        env_vars_json = f"DEPLOYMENT_VARS: '{env_vars_json}'"
        # for env_var_name, env_var in self.deployment_vars.items():
        #     env_string += f'{env_var_name.upper()}: "{env_var}"\n'
        env_vars_json = textwrap.indent(env_vars_json, " " * 24)

        github_actions_script = textwrap.dedent(
            f"""\
        name: {self.github_action_workflow_name}

        on: workflow_dispatch

        jobs:
            docker:
                runs-on: ubuntu-latest
                env:
                    \n{secret_string}
                    \n{env_vars_json}
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
                            key: ${{{{  runner.os }}}}-pip-${{{{  hashFiles('**deployments/{self.deployment_name}/requirements.txt') }}}}
                            restore-keys: |
                                ${{{{  runner.os }}}}-pip-

                    - name: Install dependencies
                        run: |
                            python -m pip install --upgrade pip
                            if [ -f deployments/{self.deployment_name}/requirements.txt ]; then pip install -r deployments/{self.deployment_name}/requirements.txt; fi

                    - name: Login to Docker registry
                        uses: docker/login-action@v2 
                        with:
                            registry: {self.docker_registry}
                            username: {self.docker_username}
                            password: ${{{{  secrets.{self.deployment_name.upper()}_DOCKER_TOKEN }}}}

                    - name: Build and push Docker image
                        uses: docker/build-push-action@v4
                        with:
                            context: .
                            file: deployments/{self.deployment_name}/Dockerfile
                            push: true
                            tags: {self.docker_image_path}

                    - name: Add execute permissions to the script
                        run: chmod +x app/deployment_maker/deploy_stackpath_container.py

                    - name: Run deployment script
                        run: app/deployment_maker/deploy_stackpath_container.py
        """
        )

        github_actions_script = github_actions_script.replace("    ", "  ")
        os.makedirs(".github/workflows", exist_ok=True)
        # with open(f'.github/workflows/{deployment_settings.github_action_workflow_name}.yaml', 'w') as f:
        with open(
            f".github/workflows/{self.deployment_name}_deployment.yaml", "w", encoding="utf-8") as f:
            f.write(github_actions_script)
    
    
            