import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

class BaseClass:
    
    deployment_name: str = None
    
    @staticmethod
    def load_and_check_list(var, moniker_name=None):
        if moniker_name is None:
            potential_vars = DeploymentClass.get_and_convert_env_vars(f"{BaseClass.deployment_name.upper()}_{var.upper()}")
        else:
            potential_vars = DeploymentClass.get_and_convert_env_vars(f"{BaseClass.deployment_name.upper()}_{moniker_name.upper()}_{var.upper()}")
        if potential_vars is None or potential_vars == []:
            raise ValueError(f"No list items for: {var}")
        potential_vars = [
            str(id).strip() for id in potential_vars.split(",") if id.strip()
        ]
        for potential_var in potential_vars:
            if potential_var is None or potential_var == "":
                raise ValueError(f"Invalid list item in: {var}")
        return potential_vars
    
    @staticmethod
    def get_and_convert_env_vars(env_var_name=None):
        # If None pulls from .env for container deployments
        # Other wise it paths to deployment folder
        env_value = os.getenv(env_var_name)
        if env_value is not None and env_value.lower() != "none" and env_value != "":
            if isinstance(env_value, bool):
                return env_value
            if env_value.lower() in ("yes", "true", "t", "y", "1"):
                return True
            elif env_value.lower() in ("no", "false", "f", "n", "0"):
                return False
            else:
                return env_value
        return None
    
    @staticmethod
    def check_required_vars(instance):
        for var in instance.required_vars:
            if not var.startswith("_") and not callable(getattr(instance, var)):
                value = getattr(instance, var, None)
                if value is None or value == "":
                    raise ValueError(
                        f"{var} is not set or is an empty string after loading environment variables"
                    )
    
    @staticmethod
    def merge_vars_to_instance(instance, config):
        for var, val in vars(config).items():
            if not var.startswith("_") and not callable(getattr(config, var)):
                # If both are None still add the var to the moniker class so we can catch the error
                if getattr(instance, var, None) is not None and val is None:
                    continue
            setattr(instance, var, val)
              
class DeploymentClass(BaseClass):
    # Initialized with deployment_name as an arg
    deployment_name: str = None
    enabled_moniker_names: list = []
    enabled_sprite_names: list = []
    monikers: dict = {}
    
    DEVOPS_VARIABLES = [
        "docker_token",
        "stackpath_client_id",
        "stackpath_api_client_secret",
        "docker_username",
        "docker_repo",
    ]
    SECRET_VARIABLES = [
        "docker_token",
        "stackpath_client_id",
        "stackpath_api_client_secret",
    ]
    
    required_vars = []
    
    @classmethod
    def load_and_check_deployment(cls, deployment_name):
        from sprites.discord_sprite import DiscordConfig
        from services.shelby_agent import ShelbyConfig
        cls.deployment_name = deployment_name
        # Confirm env is loaded for deployment names
        DeploymentClass.load_deployment_name()
        
        # Get and and load monikers
        cls.enabled_moniker_names = DeploymentClass.load_and_check_list('enabled_moniker_names')
        cls.enabled_sprite_names = DeploymentClass.load_and_check_list('enabled_sprite_names')
 
        for sprite_name in cls.enabled_sprite_names:
            match sprite_name:
                case 'discord':
                    cls.load_deployment_services(DiscordConfig(), 'DISCORDSPRITE')
                    cls.load_deployment_services(ShelbyConfig(), 'DISCORDSPRITE')

        for moniker_name in cls.enabled_moniker_names:
            cls.monikers[moniker_name] = Moniker(moniker_name=moniker_name)

        # Check that all class vars are initialized 
        for var in vars(__class__):
            if not var.startswith("_") and not callable(getattr(cls, var)):
                cls.required_vars.append(var)
        
        BaseClass.check_required_vars(cls)
    
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
    
    @classmethod
    def load_deployment_services(cls, data_class, sprite):
        deployment = BaseClass.deployment_name.upper()
        for var in list(vars(data_class).keys()):
            if var.startswith("_") and callable(getattr(data_class, var)):
                continue
            env_var_name = f"{deployment}_{sprite.upper()}_{var.upper()}"
            env_value = BaseClass.get_and_convert_env_vars(env_var_name)
            if env_value is not None:
                setattr(data_class, var, env_value)
        data_class.load_class_config()
        data_class.check_class_config()
        BaseClass.merge_vars_to_instance(cls, data_class)
        
@dataclass
class Moniker(BaseClass):
    
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
    
    required_vars: list = field(default_factory=list)
    
    def __post_init__(self):
        self.load_and_check_moniker()
        
    def load_and_check_moniker(self):
        from sprites.discord_sprite import DiscordConfig
        from services.shelby_agent import ShelbyConfig
        self.load_moniker_vars()
        if self.moniker_enabled is False:
            raise ValueError(f"Moniker disabled: {self.moniker_name}")
        self.enabled_sprite_names = Moniker.load_and_check_list('enabled_sprite_names', self.moniker_name)
        self.enabled_data_namespaces = Moniker.load_and_check_list('enabled_data_namespaces', self.moniker_name)
        # Check that all class vars are initialized 
        for var in vars(self):
            if not var.startswith("_") and not callable(getattr(self, var)):
                self.required_vars.append(var)
                
        BaseClass.check_required_vars(self)
        # Load variables that are defined specifically for the moniker's sprites
        for sprite_name in self.enabled_sprite_names:
            match sprite_name:
                case 'discord':
                    self.load_moniker_services(DiscordConfig(), 'DISCORDSPRITE')
                    self.load_moniker_services(ShelbyConfig(), 'DISCORDSPRITE')
        
    def load_moniker_vars(self):
        deployment = BaseClass.deployment_name.upper()
        moniker = self.moniker_name.upper()
        for var in list(vars(self).keys()):
            if var.startswith("_") and callable(getattr(self, var)):
                continue
            env_var_name = f"{deployment}_{moniker}_{var.upper()}"
            env_value = BaseClass.get_and_convert_env_vars(env_var_name)
            if env_value is not None:
                setattr(self, var, env_value)
    
    def load_moniker_services(self, data_class, sprite):
        deployment = BaseClass.deployment_name.upper()
        moniker = self.moniker_name.upper()
        for var in list(vars(data_class).keys()):
            if var.startswith("_") and callable(getattr(data_class, var)):
                continue
            env_var_name = f"{deployment}_{moniker}_{sprite.upper()}_{var.upper()}"
            env_value = BaseClass.get_and_convert_env_vars(env_var_name)
            if env_value is not None:
                setattr(data_class, var, env_value)
        data_class.load_class_config()
        BaseClass.merge_vars_to_instance(self, data_class)
    
