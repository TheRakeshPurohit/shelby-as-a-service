import os

class BaseClass:
    
    deployment_name: str = None
    
    @staticmethod
    def get_and_convert_env_var(env_var_name=None):
        # If None pulls from .env for container deployments
        # Other wise it paths to deployment folder
        env_value = os.getenv(env_var_name)
        env_value = BaseClass.parse_env_variable(env_value)
        if env_value is None:
            return None
        if isinstance(env_value, str):
            env_value = BaseClass.check_str_for_list(env_value)
        if env_value is None:
            return None
        return env_value
    
    @staticmethod
    def load_existing_env_file(filepath):
        env_vars = {}
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    env_var, env_value = line.strip().split("=", 1)
                except ValueError:
                    # ignore lines that don't contain an equals sign
                    continue
                env_value = BaseClass.parse_env_variable(env_value)
                if env_value is None:
                    continue
                if isinstance(env_value, str):
                    env_value = BaseClass.check_str_for_list(env_value)
                if env_value is None:
                    continue
                env_vars[env_var] = env_value
        return env_vars
    
    @staticmethod
    def parse_env_variable(env_var):
        if env_var is None or env_var.lower() == "none" or env_var == "":
            return None
        if env_var.lower() in ("yes", "true", "t", "y"):
            return True
        if env_var.lower() in ("no", "false", "f", "n"):
            return False
        # try to convert to int or float
        try:
            # check for integer
            env_var = int(env_var)
            return env_var
        except ValueError:
            try:
                # if not integer, check for float
                env_var = float(env_var)
            except ValueError:
                # if it's neither, leave it as is
                pass
        return env_var
    
    @staticmethod
    def check_str_for_list(env_var):
        env_var = env_var.strip().split(",")
        if len(env_var) == 1:
            # Not a list, so skip.
            return env_var[0]
        env_var_list = []
        for split in env_var:
            env_var_list.append(BaseClass.parse_env_variable(split))
        return env_var
            
    @staticmethod 
    def load_and_check_env_list(var, moniker_name=None):
        if moniker_name is None:
            return BaseClass.get_and_convert_env_var(f"{BaseClass.deployment_name.upper()}_{var.upper()}")
        else:
            return BaseClass.get_and_convert_env_var(f"{BaseClass.deployment_name.upper()}_{moniker_name.upper()}_{var.upper()}")
        
    @staticmethod
    def parse_env_int_list(env_var):
        if isinstance(env_var, str):
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
        if instance.MONIKER_REQUIRED_VARIABLES_:
            for req in instance.MONIKER_REQUIRED_VARIABLES_:
                if req not in moniker_env_vars:
                    raise ValueError(
                        f"Error: required config var missing at moniker level: {req}"
                    )
        if instance.MONIKER_REQUIRED_VARIABLES_:
            for req in instance.MONIKER_REQUIRED_VARIABLES_:
                if req in deployment_env_vars:
                    raise ValueError(
                        f"Error: config var must be set at moniker level: {req}"
                    )
        # Deployment_env_vars
        if instance.DEPLOYMENT_REQUIRED_VARIABLES_:
            for req in instance.DEPLOYMENT_REQUIRED_VARIABLES_:
                if req in moniker_env_vars:
                    raise ValueError(
                        f"Error: config var must be set at deployment level: {req}"
                    )
        if instance.DEPLOYMENT_REQUIRED_VARIABLES_:
            for req in instance.DEPLOYMENT_REQUIRED_VARIABLES_:
                if req not in deployment_env_vars:
                    raise ValueError(
                        f"Error: required config var missing at deployment level: {req}"
                    )
                value = moniker_env_vars.get(req)
                
    @staticmethod
    def check_class_required_vars(instance):
        for var in vars(instance):
            if not var.startswith("_") and not var.endswith("_") and not callable(getattr(instance, var)):
                value = getattr(instance, var, None)
                if value is None or value == "":
                    raise ValueError(
                        f"{var} is not set or is an empty string after loading environment variables"
                    )
    
    @staticmethod
    def check_required_vars_list(instance, required_vars):
        for var in required_vars:
            if not var.startswith("_") and not var.endswith("_") and not var.endswith("_"):
                value = getattr(instance, var, None)
                if value is None or value == "":
                    raise ValueError(
                        f"{var} is not set or is an empty string after loading environment variables"
                    )
    
    @staticmethod
    def merge_vars_to_instance(sprite_config, class_config):
        for var, val in vars(class_config).items():
            if not var.startswith("_") and not var.endswith("_") and not callable(getattr(class_config, var)):
                if var in sprite_config:
                    raise ValueError(f"{var} from {class_config.__class__.__name__} already exists in sprite_config!")
                sprite_config[var] = val
        return sprite_config
    
    @staticmethod
    def load_service_config(sprite_config, service_config, service_instance):
        for var, _ in vars(service_config).items_():
            if not var.startswith("_") and not var.endswith("_") and not callable(getattr(service_config, var)):
                sprite_val = getattr(sprite_config, var, None)
                if sprite_val is None:
                    raise ValueError(f"{var} not found in sprite_config for {service_instance.__class__.__name__}")
                setattr(service_instance, var, sprite_val)
        return sprite_config
        