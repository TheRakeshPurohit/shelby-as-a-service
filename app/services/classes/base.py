import os

class BaseClass:
    
    deployment_name: str = None
    
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
    def load_and_check_env_list(var, moniker_name=None):
        if moniker_name is None:
            potential_vars = BaseClass.get_and_convert_env_vars(f"{BaseClass.deployment_name.upper()}_{var.upper()}")
        else:
            potential_vars = BaseClass.get_and_convert_env_vars(f"{BaseClass.deployment_name.upper()}_{moniker_name.upper()}_{var.upper()}")
        
        return BaseClass.parse_env_string_list(potential_vars)
    
    @staticmethod
    def parse_env_string_list(env_var):
        if not isinstance(env_var, str):
            potential_vars = [
                str(id).strip() for id in env_var.split(",") if id.strip()
            ]
        else:
            potential_vars = env_var
        if potential_vars is None or potential_vars == []:
            raise ValueError(f"No list items for: {env_var}")
        for potential_var in potential_vars:
            if potential_var is None or potential_var == "":
                raise ValueError(f"Invalid list item in: {env_var}")
        return potential_vars
    
    @staticmethod
    def parse_env_int_list(env_var):
        if not isinstance(env_var, list):
            potential_vars = [
                int(id.strip()) for id in env_var.split(",") if id.strip()
            ]
        else:
            potential_vars = env_var
        if potential_vars is None or potential_vars == []:
            raise ValueError(f"No list items for: {env_var}")
        for potential_var in potential_vars:
            if potential_var is None or potential_var == "":
                raise ValueError(f"Invalid list item in: {env_var}")
        return potential_vars
        
    @staticmethod
    def check_required_env_vars(instance, moniker_env_vars, deployment_env_vars):
        # Moniker_env_vars
        if instance.MONIKER_REQUIRED_VARIABLES:
            for req in instance.MONIKER_REQUIRED_VARIABLES:
                if req not in moniker_env_vars:
                    raise ValueError(
                        f"Error: required config var missing at moniker level: {req}"
                    )
        if instance.DEPLOYMENT_REQUIRED_VARIABLES:
            for req in instance.DEPLOYMENT_REQUIRED_VARIABLES:
                if req in moniker_env_vars:
                    raise ValueError(
                        f"Error: config var must be set at deployment level: {req}"
                    )
        # Deployment_env_vars
        if instance.DEPLOYMENT_REQUIRED_VARIABLES:
            for req in instance.DEPLOYMENT_REQUIRED_VARIABLES:
                if req not in deployment_env_vars:
                    raise ValueError(
                        f"Error: required config var missing at deployment level: {req}"
                    )
        if instance.MONIKER_REQUIRED_VARIABLES:
            for req in instance.MONIKER_REQUIRED_VARIABLES:
                if req in deployment_env_vars:
                    raise ValueError(
                        f"Error: config var must be set at moniker level: {req}"
                    )

    @staticmethod
    def check_class_required_vars(instance):
        for var in vars(instance):
            if not var.startswith("_") and not callable(getattr(instance, var)):
                value = getattr(instance, var, None)
                if value is None or value == "":
                    raise ValueError(
                        f"{var} is not set or is an empty string after loading environment variables"
                    )
    
    @staticmethod
    def check_required_vars_list(required_vars):
        for var in required_vars:
            if not var.startswith("_"):
                value = getattr(required_vars, var, None)
                if value is None or value == "":
                    raise ValueError(
                        f"{var} is not set or is an empty string after loading environment variables"
                    )
    
    @staticmethod
    def merge_vars_to_instance(sprite_config, class_config):
        for var, val in vars(class_config).items():
            if not var.startswith("_") and not callable(getattr(class_config, var)):
                if var in sprite_config:
                    raise ValueError(f"{var} from {class_config.__class__.__name__} already exists in sprite_config!")
                setattr(sprite_config, var, val)
        return sprite_config
    
    @staticmethod
    def load_service_config(sprite_config, service_config, service_instance):
        for var, _ in vars(service_config).items_():
            if not var.startswith("_") and not callable(getattr(service_config, var)):
                sprite_val = getattr(sprite_config, var, None)
                if sprite_val is None:
                    raise ValueError(f"{var} not found in sprite_config for {service_instance.__class__.__name__}")
                setattr(service_instance, var, sprite_val)
        return sprite_config
        