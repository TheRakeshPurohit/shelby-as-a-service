import os
import json
import yaml
from dotenv import load_dotenv

class BaseClass:
    """Interface"""
    load_dotenv()
    stackpath_client_id = None
    stackpath_api_client_secret = None
    openai_api_key = None
    pinecone_api_key = None
    docker_token = None
    deployment_name = None
    deployment_sprites = None
    with open(os.path.join(f'index/personal_index_config.yaml'), 'r') as stream:
        data_sources = yaml.safe_load(stream)
    
    def __init__(self, **kwargs):
        self.vars = {k: v for k, v in vars(self.__class__).items() if not k.startswith('__')} 
        for k, v in kwargs.items():
            if k in self.vars:
                self.vars[k] = v

    @classmethod
    def LoadVarsFromEnv(cls, modifier=None):
        for var, _ in vars(cls).items():
            if not var.startswith('_') and not callable(getattr(cls, var)):
                env_var_name = f'{modifier.upper()}_{var.upper()}' if modifier else var.upper()
                env_value = os.getenv(env_var_name)
                if env_value is not None:
                    setattr(cls, var, env_value) 
                
    @classmethod
    def CheckRequiredVars(cls, required_vars):
        for var in required_vars:
            if not var.startswith('_') and not callable(getattr(cls, var)):
                value = getattr(cls, var, None)
                if value is None or value == '':
                    raise ValueError(f"{var} is not set or is an empty string after loading environment variables")

BaseClass.LoadVarsFromEnv()
BaseClass.deployment_sprites = json.loads(BaseClass.deployment_sprites)
BaseClass.CheckRequiredVars([var for var in vars(BaseClass) if not var.startswith('__')])

