import os
import json
import yaml
from dotenv import load_dotenv

class BaseClass:

    _SECRET_VARIABLES: list = [
        'docker_token',
        'stackpath_client_id',
        'stackpath_api_client_secret',
        'openai_api_key',
        'pinecone_api_key'
        ]
    _DEVOPS_VARIABLES: list = [
        'deployment_monikers_sprites',
        'stackpath_client_id',
        'docker_token',
        'index_available_namespaces',
        'index_description',
        ]
    _EXTERNAL_SERVICES_VARIABLES: list = [
        'index_available_namespaces',
        'openai_api_key',
        'pinecone_api_key',
        'pinecone_env',
        'pinecone_index',
        ]
    
    @classmethod
    def _initialize(cls):
        unique_variables = list(set(cls._SECRET_VARIABLES + cls._DEVOPS_VARIABLES + cls._EXTERNAL_SERVICES_VARIABLES))
        cls._REQUIRED_VARIABLES = unique_variables
        for var in unique_variables:
            setattr(cls, var, None)

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
                if env_value is None:                 
                    env_var_name = f'{var.upper()}'
                    env_value = os.getenv(env_var_name)
                if env_value is not None:
                    setattr(cls, var, env_value)
                    
                # Special rules due to limitation of .env vars
                if var == 'deployment_monikers_sprites':
                    BaseClass.deployment_monikers_sprites = json.loads(BaseClass.deployment_monikers_sprites)
                if var == 'index_available_namespaces':
                    BaseClass.index_available_namespaces = BaseClass.index_available_namespaces.split(',')
                if var == 'index_description':
                    with open(f'index/index_description.yaml', 'r') as stream:
                        BaseClass.index_description = yaml.safe_load(stream)
        
    @classmethod
    def CheckRequiredVars(cls, required_vars):
        for var in required_vars:
            if not var.startswith('_') and not callable(getattr(cls, var)):
                value = getattr(cls, var, None)
                if value is None or value == '':
                    raise ValueError(f"{var} is not set or is an empty string after loading environment variables")
                
    @classmethod
    def LoadAndCheckEnvVars(cls):
        # First, it loads the environment variables.
        load_dotenv()
        cls.deployment_name = os.getenv('DEPLOYMENT_NAME')
        if cls.deployment_name is None or cls.deployment_name == '':
            raise ValueError("No deployment found. Try run.py --config 'new deployment name'")
        cls.deployment_check = os.getenv('DEPLOYMENT_POPULATED')
        if cls.deployment_check is None or cls.deployment_check is False:
            raise ValueError("Please set all required vars in .env in specified deployment folder. Then set 'DEPLOYMENT_POPULATED'=True to continue.")

        # It then loads the rest of the class variables.
        cls.LoadVarsFromEnv()

        # And finally, it checks if all the required variables are set.
        cls.CheckRequiredVars([var for var in vars(cls)])
        
BaseClass._initialize()
