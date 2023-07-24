import os
import json
import yaml
from dotenv import load_dotenv

class BaseClass:
    
    openai_api_key: str = None
    pinecone_api_key: str = None
    
    _DEVOPS_VARIABLES: list = [
        'docker_token',
        'stackpath_client_id',
        'stackpath_api_client_secret',
        'docker_username',
        'docker_repo',
        ]
    _SECRET_VARIABLES: list = [
        'docker_token',
        'stackpath_client_id',
        'stackpath_api_client_secret',
        'openai_api_key',
        'pinecone_api_key',
        ]
        
    def __init__(self):
        # Creates instance variables from class variables
        for k, v in vars(self.__class__).items():
            if not k.startswith('_') and not callable(v): 
                setattr(self, k, v)
        self.LoadInstanceVarsFromEnv()

    def LoadInstanceVarsFromEnv(self):
        # Finds the most granular var available for an instance. 
        # Starting with the least specific, and overriding if a more specific var exists
        deployment = self.deployment_name.upper()
        moniker = getattr(self, 'moniker', None)
        class_name = getattr(self, 'class_name', None)
        for var, _ in vars(self).items():
            if var.startswith('_') and callable(getattr(self, var)):
                continue
            env_var_name = f'{deployment.upper()}_{var.upper()}'
            env_value = self.get_and_convert_env_vars(env_var_name)
            if env_value is not None:
                setattr(self, var, env_value)
            # Class should not be nameless
            if class_name is not None:
                env_var_name = f'{deployment.upper()}_{class_name.upper()}_{var.upper()}'
                env_value = self.get_and_convert_env_vars(env_var_name)
                if env_value is not None:
                    setattr(self, var, env_value)
                # Moniker depends on existence of class_name
                if moniker is not None:
                    env_var_name = f'{deployment.upper()}_{moniker.upper()}_{class_name.upper()}_{var.upper()}'
                    env_value = self.get_and_convert_env_vars(env_var_name)
                    if env_value is not None:
                        setattr(self, var, env_value)

    def CheckRequiredVars(self, required_vars):
        for var in required_vars:
            if not var.startswith('_') and not callable(getattr(self, var)):
                value = getattr(self, var, None)
                if value is None or value == '':
                    raise ValueError(f"{var} is not set or is an empty string after loading environment variables")

    @staticmethod
    def get_and_convert_env_vars(env_var_name=None):
        # If None pulls from .env for container deployments
        # Other wise it paths to deployment folder
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
    def InitialConfigCheck(cls, deployment_name, path=None):
        # Initial check to ensure the deployment config is set up for config or deployment
        load_dotenv(path)
        cls.deployment_name = os.getenv('DEPLOYMENT_NAME')
        if cls.deployment_name is None or cls.deployment_name == '':
            raise ValueError("No deployment found. Try run.py --config 'new deployment name'")
        cls.deployment_check = os.getenv('DEPLOYMENT_POPULATED')
        if cls.deployment_check is None or str(cls.deployment_check).lower() != 'true':
            raise ValueError(f"Please set all required vars in .env in specified deployment folder. Then set '{cls.deployment_name.upper()}_DEPLOYMENT_POPULATED'=True to continue.")

        for var in vars(cls):
            if var.startswith('_') or callable(getattr(cls, var)) or getattr(cls, var) is not None:
                continue
            
            env_var_name = f'{deployment_name.upper()}_{var.upper()}'
            env_value = cls.get_and_convert_env_vars(env_var_name)
            if env_value is not None:
                setattr(cls, var, env_value)
            else:
                raise ValueError(f"{var} is not set or is an empty string after loading environment variables")
        
            # Special rules due to limitation of .env vars
            if var == 'deployment_monikers_sprites':
                setattr(cls, 'deployment_monikers_sprites', json.loads(getattr(cls, 'deployment_monikers_sprites')))
            if var == 'index_available_namespaces':
                setattr(cls, 'index_available_namespaces', getattr(cls, 'index_available_namespaces').split(','))
            if var == 'index_description':
                with open(f'index/index_description.yaml', 'r') as stream:
                    setattr(cls, 'index_description', yaml.safe_load(stream))


