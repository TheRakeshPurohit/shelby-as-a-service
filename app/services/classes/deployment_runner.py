import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from .base import BaseClass
from .config import DiscordConfig, ShelbyConfig

class DeploymentClass(BaseClass):
    # Initialized with deployment_name as an arg
    deployment_name: str = None
    enabled_moniker_names: list = []
    monikers: dict = {}
    
    # Variables here are only populated to workflow
    DEVOPS_VARIABLES_ = [
        "docker_username",
        "docker_repo",
        "docker_token",
        "stackpath_stack_id",
        "stackpath_client_id",
        "stackpath_api_client_secret"
    ]
    
    # Adds as 'required' to deployment.env and workflow
    DEPLOYMENT_REQUIRED_VARIABLES_: list = [
        "enabled_moniker_names"
    ]
    
    # Variables here will be excluded from workflow
    # All potential secrets need to be added here
    SECRET_VARIABLES_ = [
        "docker_token",
        "stackpath_client_id",
        "stackpath_api_client_secret",
        "openai_api_key",
        "pinecone_api_key",
        "discord_bot_token",
        "slack_bot_token",
        "slack_app_token"
    ]
    
    # Avoids circular imports by having class reqs as strings
    CLASSES_ = {
    'ShelbyConfig': ShelbyConfig,
    'DiscordConfig': DiscordConfig
    }
    
    @classmethod
    def load_and_check_deployment(cls, deployment_name):

        cls.deployment_name = deployment_name
        # Confirm env is loaded for deployment names
        DeploymentClass.load_deployment_name()
        
        # Get and and load monikers
        cls.enabled_moniker_names = BaseClass.get_and_convert_env_list(f'{cls.deployment_name}_enabled_moniker_names')

        for moniker_name in cls.enabled_moniker_names:
            cls.monikers[moniker_name] = MonikerClass(moniker_name=moniker_name)

        BaseClass.check_class_required_vars(cls)
    
    @classmethod
    def load_deployment_name(cls):
        if cls.deployment_name is None or cls.deployment_name == "":
            raise ValueError(
                "No deployment arg specified."
            )
        # Initial check to ensure the deployment config is correct
        path = f"deployments/{cls.deployment_name}/{cls.deployment_name}_deployment.env"
        if os.path.exists(path):
            # For local deployment and config check
            load_dotenv(path)
        else:
            # For container deployment
            load_dotenv()
        deployment_name = os.getenv("DEPLOYMENT_NAME")
        if cls.deployment_name != deployment_name:
            raise ValueError(
                "No deployment found in env."
            )
        BaseClass.deployment_name = cls.deployment_name
      
@dataclass
class MonikerClass(DeploymentClass):
    
    moniker_name: str = field(default=None)
    moniker_enabled_sprite_names: list = field(default_factory=list)
    moniker_enabled: bool = field(default=None)
    
    # Adds as 'required' to deployment.env and workflow
    MONIKER_REQUIRED_VARIABLES_ = [
        "moniker_enabled",
        "moniker_enabled_sprite_names",
        "moniker_enabled_data_namespaces"
    ]
    
    def __post_init__(self):
        self.load_and_check_moniker()
        
    def load_and_check_moniker(self):
       
        self.load_moniker_vars()
        if self.moniker_enabled is False:
            raise ValueError(f"Moniker disabled: {self.moniker_name}")
        self.moniker_enabled_sprite_names = MonikerClass.get_and_convert_env_list(f'{self.deployment_name}_{self.moniker_name}_moniker_enabled_sprite_names')
        self.moniker_enabled_data_namespaces = MonikerClass.get_and_convert_env_list(f'{self.deployment_name}_{self.moniker_name}moniker_enabled_data_namespaces')
        
        BaseClass.check_class_required_vars(self)
        
        # Load variables that are defined specifically for the moniker's sprites
        for sprite_name in self.moniker_enabled_sprite_names:
            match sprite_name:
                case 'discord':
                    self.discord_config = self.load_moniker_services(DiscordConfig)

    def load_moniker_vars(self):
        deployment = BaseClass.deployment_name
        moniker = self.moniker_name
        for var in list(vars(self).keys()):
            if var.startswith("_") and callable(getattr(self, var)):
                continue
            env_var_name = f"{deployment}_{moniker}_{var}"
            env_value = BaseClass.get_and_convert_env_var(env_var_name)
            if env_value is not None:
                setattr(self, var, env_value)
    
    def load_moniker_services(self, sprite):
        sprite_config = {}
        # Outputs sprite_config which contains all variables from sprite and it's required classes
        deployment = DeploymentClass.deployment_name
        moniker = self.moniker_name
        sprite_name = sprite.__name__
        
        # Load vars for moniker and deployment from env
        sprite_classes = []
        # Builds list of sprite and sprite's services to iterate
        for class_name in sprite.SPRITE_REQS_:
            sprite_classes.append(sprite)
            sprite_classes.append(self.CLASSES_[class_name])
        for ClassConfig in sprite_classes:
            class_config = ClassConfig()
            deployment_env_vars = {}
            for var in list(vars(class_config).keys()):
                if var.startswith("_") and callable(getattr(class_config, var)):
                    continue
                moniker_env_var_name = f"{deployment}_{moniker}_{sprite_name}_{var}"
                moniker_env_value = BaseClass.get_and_convert_env_var(moniker_env_var_name)
                deployment_env_var_name = f"{deployment}_{sprite_name}_{var.upper()}"
                deployment_env_value = BaseClass.get_and_convert_env_var(deployment_env_var_name)
                # First we try to set class_config variable with moniker variable and then deployment variable
                if moniker_env_value is not None:
                    setattr(class_config, var, moniker_env_value)
                    continue
                # Else we default to class default settings
                setattr(class_config, var, deployment_env_value)
            
            # Special rules
            for var in class_config.DEPLOYMENT_REQUIRED_VARIABLES_:
                env_var_name = f"{self.deployment_name}_{var}"
                env_value = BaseClass.get_and_convert_env_var(env_var_name)
                deployment_env_vars[var] = env_value
            # Appends to deployment class
            for var, val in deployment_env_vars.items():
                setattr(DeploymentClass, var, val)
            for var in class_config.MONIKER_REQUIRED_VARIABLES_:
                env_var_name = f"{self.deployment_name}_{moniker}_{sprite_name}_{var}"
                env_value = BaseClass.get_and_convert_env_var(env_var_name)
                setattr(class_config, var, env_value)
                    
            class_config.check_parse_config()
            # Then merge classes to sprite_config
            BaseClass.merge_vars_to_instance(sprite_config, class_config)
            
            
        return sprite_config
    
