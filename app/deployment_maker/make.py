import os
import sys
import textwrap
import inspect
import shutil
from importlib import import_module


class DeploymentMaker:
    def __init__(self, deployment_name):
        self.deployment_name = deployment_name

        # On first run create folder, config.py, index_description, template.env
        self.create_template()
        # Exits here on first run

        # secrets from sprites, and deployment
        self.used_sprites = set()
        self.required_secrets = set()
        self.required_deployment_vars = {}
        config_module_path = f"deployments.{deployment_name}.deployment_config"
        self.config = import_module(config_module_path)
        self.load_moniker_requirments()
        self.load_deployment_requirments()
        self.generate_dockerfile()
        self.generate_pip_requirements()
        self.generate_actions_workflow()

    def create_template(self):
        dir_path = f"app/deployments/{self.deployment_name}"
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

            source1 = "app/deployments/template/deployment_config.py"
            dest1 = os.path.join(dir_path, "deployment_config.py")
            shutil.copy(source1, dest1)

            source2 = "app/deployments/template/index_description.yaml"
            dest2 = os.path.join(dir_path, "index_description.yaml")
            shutil.copy(source2, dest2)

            source3 = "app/deployments/template/template.env"
            dest3 = os.path.join(dir_path, ".env")
            shutil.copy(source3, dest3)
            print(f"Set your settings now in the templates created here: {dir_path}")
            sys.exit()

    def load_moniker_requirments(self):
        for moniker in self.config.DeploymentConfig.MonikerConfigs.__dict__:
            if not moniker.startswith("_") and not moniker.endswith("_"):
                moniker_config = getattr(
                    self.config.DeploymentConfig.MonikerConfigs, moniker
                )
                if moniker_config.enabled:
                    for _, sprite_config in moniker_config.__dict__.items():
                        if inspect.isclass(sprite_config):
                            if sprite_config.enabled:
                                self.used_sprites.add(sprite_config.model.sprite_name)
                                for secret in sprite_config.model.SECRETS_:
                                    self.required_secrets.add(secret)

    def load_deployment_requirments(self):
        for req_var in self.config.DeploymentConfig.model.DEPLOYMENT_REQUIREMENTS_:
            self.required_deployment_vars[req_var] = getattr(
                self.config.DeploymentConfig, req_var
            )
        for secret in self.config.DeploymentConfig.model.SECRETS_:
            self.required_secrets.add(secret)

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
RUN pip install --no-cache-dir -r app/deployments/{self.deployment_name}/requirements.txt

# Run Deployment
CMD ["python", "app/app.py", "--run", "{self.deployment_name}"]
        """
        with open(
            f"app/deployments/{self.deployment_name}/Dockerfile", "w", encoding="utf-8"
        ) as f:
            f.write(dockerfile)

    def generate_pip_requirements(self):
        combined_requirements = set()
        for sprite_name in self.used_sprites:
            with open(
                f"app/deployment_maker/{sprite_name}_requirements.txt",
                "r",
                encoding="utf-8",
            ) as file:
                sprite_requirements = set(file.read().splitlines())
            combined_requirements.update(sprite_requirements)

        with open(
            f"app/deployments/{self.deployment_name}/requirements.txt",
            "w",
            encoding="utf-8",
        ) as file:
            file.write("\n".join(combined_requirements))

    def generate_actions_workflow(self):
        # For github secrets
        github_secrets_string = "### Secrets ###\n"
        for secret in self.required_secrets:
            secret_name = f"{self.deployment_name.upper()}_{secret.upper()}"
            github_secrets_string += (
                f"{secret_name}:  ${{{{ secrets.{secret_name} }}}}\n"
            )
        github_secrets_string += "# Secrets in the format of 'secrets.NAME' with the 'NAME' portion added to your forked repos secrets. #"
        github_secrets_string = textwrap.indent(github_secrets_string, " " * 24)

        # For injecting into container env
        required_secrets_string = "REQUIRED_SECRETS: "
        for secret in self.required_secrets:
            required_secrets_string += f"{secret.upper()};"
        required_secrets_string = textwrap.indent(required_secrets_string, " " * 24)

        github_actions_script = textwrap.dedent(
            f"""\
        name: {self.deployment_name}-deployment

        on: workflow_dispatch

        jobs:
            docker:
                runs-on: ubuntu-latest
                env:
                    \n{github_secrets_string}
                    \n{required_secrets_string}
                      DEPLOYMENT_NAME: {self.deployment_name}

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
                            key: ${{{{ runner.os }}}}-pip-${{{{  hashFiles('**app/deployments/{self.deployment_name}/requirements.txt') }}}}
                            restore-keys: |
                                ${{{{ runner.os }}}}-pip-

                    - name: Install dependencies
                        run: |
                            python -m pip install --upgrade pip
                            if [ -f app/deployments/{self.deployment_name}/requirements.txt ]; then pip install -r app/deployments/{self.deployment_name}/requirements.txt; fi

                    - name: Login to Docker registry
                        uses: docker/login-action@v2 
                        with:
                            registry: {self.required_deployment_vars['docker_registry']}
                            username: {self.required_deployment_vars['docker_username']}
                            password: ${{{{ secrets.{self.deployment_name.upper()}_DOCKER_TOKEN }}}}

                    - name: Build and push Docker image
                        uses: docker/build-push-action@v4
                        with:
                            context: .
                            file: app/deployments/{self.deployment_name}/Dockerfile
                            push: true
                            tags: {self.required_deployment_vars['docker_username']}/{self.required_deployment_vars['docker_repo']}:{self.deployment_name}-latest

                    - name: Add execute permissions to the script
                        run: chmod +x app/app.py

                    - name: Run deployment script
                        run: python app/app.py --deploy_container {self.deployment_name}
        """
        )

        github_actions_script = github_actions_script.replace("    ", "  ")
        os.makedirs(".github/workflows", exist_ok=True)
        # with open(f'.github/workflows/{deployment_settings.github_action_workflow_name}.yaml', 'w') as f:
        with open(
            f".github/workflows/{self.deployment_name}_deployment.yaml",
            "w",
            encoding="utf-8",
        ) as f:
            f.write(github_actions_script)
