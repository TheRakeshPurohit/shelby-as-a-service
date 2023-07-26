import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from .base import BaseClass
from .config import DiscordConfig, ShelbyConfig

class DeploymentClass(BaseClass):
    # Initialized with deployment_name as an arg
    deployment_name: str = None
    enabled_moniker_names: list = []
    enabled_sprite_names: list = []
    monikers: dict = {}
    
    _DEVOPS_VARIABLES = [
        "docker_token",
        "stackpath_client_id",
        "stackpath_api_client_secret",
        "docker_username",
        "docker_repo",
    ]
    _SECRET_VARIABLES = [
        "docker_token",
        "stackpath_client_id",
        "stackpath_api_client_secret",
    ]
    _DISCORD_REQS = [
        DiscordConfig,
        ShelbyConfig
    ]
    
    
    @classmethod
    def load_and_check_deployment(cls, deployment_name):


        cls.deployment_name = deployment_name
        # Confirm env is loaded for deployment names
        DeploymentClass.load_deployment_name()
        
        # Get and and load monikers
        cls.enabled_moniker_names = BaseClass.load_and_check_env_list('enabled_moniker_names')
        cls.enabled_sprite_names = BaseClass.load_and_check_env_list('enabled_sprite_names')
 
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
        path = f"app/deployments/{cls.deployment_name}/{cls.deployment_name}_deployment.env"
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
    enabled_sprite_names: list = field(default_factory=list)
    
    moniker_enabled: bool = field(default=None)
    index_name: str = field(default=None)
    index_env: str = field(default=None)
    openai_api_key: str = field(default=None)
    pinecone_api_key: str = field(default=None)
    
    _SECRET_VARIABLES: list = field(default_factory=lambda: [
        "openai_api_key",
        "pinecone_api_key",
    ])
    
    def __post_init__(self):
        self.load_and_check_moniker()
        
    def load_and_check_moniker(self):
       
        self.load_moniker_vars()
        if self.moniker_enabled is False:
            raise ValueError(f"Moniker disabled: {self.moniker_name}")
        self.enabled_sprite_names = MonikerClass.load_and_check_env_list('enabled_sprite_names', self.moniker_name)
        self.enabled_data_namespaces = MonikerClass.load_and_check_env_list('enabled_data_namespaces', self.moniker_name)
        
        BaseClass.check_class_required_vars(self)
        
        # Load variables that are defined specifically for the moniker's sprites
        for sprite_name in self.enabled_sprite_names:
            match sprite_name:
                case 'discord':
                    self.discord_config = self.load_moniker_services(DeploymentClass._DISCORD_REQS)


    def load_moniker_vars(self):
        deployment = BaseClass.deployment_name.upper()
        moniker = self.moniker_name.upper()
        for var in list(vars(self).keys()):
            if var.startswith("_") and callable(getattr(self, var)):
                continue
            if var not None:
                continue
            env_var_name = f"{deployment}_{moniker}_{var.upper()}"
            env_value = BaseClass.get_and_convert_env_vars(env_var_name)
            if env_value is not None:
                setattr(self, var, env_value)
    
    def load_moniker_services(self, sprite_reqs):
        deployment = DeploymentClass.deployment_name.upper()
        moniker = self.moniker_name.upper()
        # Outputs sprite_config which contains all variables from sprite and it's required classes
        sprite_config = {}
        # Load vars for moniker and deployment from env
        for ClassConfig in sprite_reqs:
            moniker_env_vars = {}
            deployment_env_vars = {}
            class_config = ClassConfig()
            class_name = class_config.__class__.__name__.upper()
            for var in list(vars(class_config).keys()):
                if var.startswith("_") and callable(getattr(class_config, var)):
                    continue
                moniker_env_var_name = f"{deployment}_{moniker}_{class_name}_{var.upper()}"
                moniker_env_value = BaseClass.get_and_convert_env_vars(moniker_env_var_name)
                deployment_env_var_name = f"{deployment}_{class_name}_{var.upper()}"
                deployment_env_value = BaseClass.get_and_convert_env_vars(deployment_env_var_name)
                # First we try to set class_config variable with moniker variable and then deployment variable
                if moniker_env_value is not None:
                    moniker_env_vars[var] = moniker_env_value
                    setattr(class_config, var, moniker_env_value)
                elif deployment_env_value is not None:
                    deployment_env_vars[var] = deployment_env_value
                    setattr(class_config, var, deployment_env_value)
                # Else we default to class default settings
            # Check required env_vars exist
            BaseClass.check_required_env_vars(class_config, moniker_env_vars, deployment_env_vars)
            class_config.check_parse_config()
            # Then merge classes to sprite_config
            BaseClass.merge_vars_to_instance(sprite_config, class_config)
            
        return sprite_config
    
