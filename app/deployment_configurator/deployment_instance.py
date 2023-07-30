import os
from dataclasses import dataclass, field
from typing import Optional
import yaml
from dotenv import load_dotenv
from .shared_tools import ConfigSharedTools
from .data_classes import DiscordConfig, ShelbyConfig, IndexConfig

class DeploymentInstance:
    # Initialized with deployment_name as an arg
    deployment_name: str = None
    enabled_moniker_names: list = []
    monikers: dict = {}
    used_sprites: set = set()
    used_services: set = set()

    # Variables here are only populated to workflow
    DEVOPS_VARIABLES_ = [
        "docker_registry",
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
    def load_and_check_deployment(cls, deployment_name, run_index_management=False):

        cls.deployment_name = deployment_name
        # Confirm env is loaded for deployment names
        DeploymentInstance.load_deployment_name()
        
        if run_index_management:
            cls.index_config = MonikerInstance.load_moniker_services(cls, IndexConfig)
        else:
            # Get and and load monikers
            cls.enabled_moniker_names = ConfigSharedTools.get_and_convert_env_list(f'{cls.deployment_name}_enabled_moniker_names')
            for moniker_name in cls.enabled_moniker_names:
                moniker = MonikerInstance(moniker_name=moniker_name)
                moniker.load_and_check_moniker()
                cls.monikers[moniker_name] = moniker

        ConfigSharedTools.check_class_required_vars(cls)
    
    @classmethod
    def load_deployment_name(cls):
        print(cls.deployment_name)
        if cls.deployment_name is None or cls.deployment_name == "":
            raise ValueError(
                "No deployment arg specified."
            )
        # Initial check to ensure the deployment config is correct
        path = f"deployments/{cls.deployment_name}/{cls.deployment_name}_deployment.env"
        if os.path.exists(path):
            print(path)
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
        ConfigSharedTools.deployment_name = cls.deployment_name
      
@dataclass
class MonikerInstance(DeploymentInstance):
    
    moniker_name: str = field(default=None)
    moniker_enabled: bool = field(default=None)
    moniker_enabled_sprite_names: list = field(default_factory=list)
    moniker_enabled_data_domains: dict = field(default_factory=dict)
    discord_config: Optional[dict] = field(default_factory=dict)
    
    # Adds as 'required' to deployment.env and workflow
    MONIKER_REQUIRED_VARIABLES_ = [
        "moniker_enabled",
        "moniker_enabled_sprite_names",
        "moniker_enabled_data_domains"
    ]
    
    def load_and_check_moniker(self):
        
        
        self.moniker_enabled = ConfigSharedTools.get_and_convert_env_var(f'{self.deployment_name}_{self.moniker_name}_moniker_enabled')
        self.moniker_enabled_sprite_names = ConfigSharedTools.get_and_convert_env_list(f'{self.deployment_name}_{self.moniker_name}_moniker_enabled_sprite_names')
        self.moniker_enabled_data_domains = ConfigSharedTools.get_and_convert_env_list(f'{self.deployment_name}_{self.moniker_name}_moniker_enabled_data_domains')
        
        with open(f"deployments/{self.deployment_name}/index/index_description.yaml", 'r', encoding="utf-8") as stream:
                    index_description_file = yaml.safe_load(stream)
                    
        enabled_data_domains = {}
        # Iterate over each source aka namespace
        for _, moniker in index_description_file['monikers'].items():
            for data_domain_name, domain in moniker['data_domains'].items():
                if data_domain_name in self.moniker_enabled_data_domains:
                    domain_description = domain['description']
                    enabled_data_domains[data_domain_name] = domain_description
        self.moniker_enabled_data_domains = enabled_data_domains
        
        # Load variables that are defined specifically for the moniker's sprites
        for sprite_name in self.moniker_enabled_sprite_names:
            match sprite_name:
                case 'discord':
                    self.discord_config = self.load_moniker_services(DiscordConfig)
                    
        ConfigSharedTools.check_class_required_vars(self)
    
    def load_moniker_services(self, sprite):
        deployment = DeploymentInstance.deployment_name
        moniker = getattr(self, 'moniker_name', None)

        sprite_name = sprite.__name__
        
        # Outputs sprite_config which contains all requried data classes for sprite
        sprite_config = {}
        # Load vars for moniker and deployment from env
        sprite_classes = []
        # Builds list of sprite and sprite's services to iterate
        if getattr(sprite, 'SPRITE_REQS_', None):
            for class_name in sprite.SPRITE_REQS_:
                sprite_classes.append(self.CLASSES_[class_name])
                DeploymentInstance.used_services.add(self.CLASSES_[class_name])
        sprite_classes.append(sprite)
        DeploymentInstance.used_sprites.add(sprite)
            
        for ClassConfig in sprite_classes:
            class_config = ClassConfig()
            class_name = class_config.__class__.__name__
            deployment_env_vars = {}
            for var in list(vars(class_config).keys()):
                if var.startswith("_") and callable(getattr(class_config, var)):
                    continue
                moniker_env_var = f"{deployment}_{moniker}_{sprite_name}_{var}"
                moniker_env_value = ConfigSharedTools.get_and_convert_env_var(moniker_env_var)
                deployment_overrides_env_var = f"{deployment}_{sprite_name}_{var}"
                deployment_overrides_env_value = ConfigSharedTools.get_and_convert_env_var(deployment_overrides_env_var)
                deployment_defaults_env_var = f"{deployment}_{class_name}_{var}"
                deployment_defaults_env_value = ConfigSharedTools.get_and_convert_env_var(deployment_defaults_env_var)
                # First we try to set class_config variable with moniker variable and then deployment variable
                if moniker_env_value is not None:
                    setattr(class_config, var, moniker_env_value)
                    continue
                elif deployment_overrides_env_value is not None:
                    setattr(class_config, var, deployment_overrides_env_value)
                    continue
                elif deployment_defaults_env_value is not None:
                    setattr(class_config, var, deployment_defaults_env_value)
                    continue
                # Else we default to class default settings
       
            # Special rules
            for var in class_config.DEPLOYMENT_REQUIRED_VARIABLES_:
                env_var_name = f"{self.deployment_name}_{var}"
                env_value = ConfigSharedTools.get_and_convert_env_var(env_var_name)
                deployment_env_vars[var] = env_value
            # Appends to deployment class
            for var, val in deployment_env_vars.items():
                setattr(DeploymentInstance, var, val)
            for var in class_config.MONIKER_REQUIRED_VARIABLES_:
                env_var_name = f"{self.deployment_name}_{moniker}_{sprite_name}_{var}"
                env_value = ConfigSharedTools.get_and_convert_env_var(env_var_name)
                setattr(class_config, var, env_value)
                    
            class_config.check_parse_config()
            sprite_config[f"{class_config.__class__.__name__}"] = class_config
    
        return sprite_config
    
