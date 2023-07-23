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
        'stackpath_api_client_secret',
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

    @staticmethod
    def get_env_var_value(env_var_name):

        env_value = os.getenv(env_var_name)
        if env_value is not None and env_value.lower() != 'none':
            if isinstance(env_value, bool):
                return env_value
            if env_value.lower() in ('yes', 'true', 't', 'y', '1'):
                return True
            elif env_value.lower() in ('no', 'false', 'f', 'n', '0'):
                return False
            else:
                return env_value
        return None
    
    @classmethod
    def LoadVarsFromEnv(cls, moniker=None, class_name=None):
        # Add secret variables to the list of vars to be checked
        all_vars = []
        for var, _ in vars(cls).items():
            if not var.startswith('_') and not callable(getattr(cls, var, None)):
                all_vars.append((var, None))
        all_vars += [(var, None) for var in cls._SECRET_VARIABLES]
        # Tries to find var in env from most specific pattern to least specific
        for var, _ in all_vars:
            base_name = f'{cls.deployment_name.upper()}'
            if moniker and class_name:
                env_var_name = f'{base_name}_{moniker.upper()}_{class_name.upper()}_{var.upper()}'
                env_value = cls.get_env_var_value(env_var_name)
                if env_value is not None:
                    setattr(cls, var, env_value)
                    continue
            if class_name:
                env_var_name = f'{base_name}_{class_name.upper()}_{var.upper()}'
                env_value = cls.get_env_var_value(env_var_name)
                if env_value is not None:
                    setattr(cls, var, env_value)
                    continue
            env_var_name = f'{base_name}_{var.upper()}'
            env_value = cls.get_env_var_value(env_var_name)
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
    def LoadAndCheckEnvVars(cls, deployment_name):
        path = f'app/deployments/{deployment_name}/{deployment_name}.env'
        load_dotenv(path)
        cls.deployment_name = os.getenv('DEPLOYMENT_NAME')
        if cls.deployment_name is None or cls.deployment_name == '':
            raise ValueError("No deployment found. Try run.py --config 'new deployment name'")
        cls.deployment_check = os.getenv(f'{cls.deployment_name.upper()}_DEPLOYMENT_POPULATED')
        if cls.deployment_check is None or cls.deployment_check is False:
            raise ValueError(f"Please set all required vars in .env in specified deployment folder. Then set '{cls.deployment_name.upper()}_DEPLOYMENT_POPULATED'=True to continue.")

        # It then loads the rest of the class variables.
        cls.LoadVarsFromEnv()

        # And finally, it checks if all the required variables are set.
        cls.CheckRequiredVars([var for var in vars(cls)])
        
BaseClass._initialize()
