import os
import ast

class ConfigSharedTools:
    
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
                env_value = ConfigSharedTools.parse_env_variable(env_value)
                if env_value is None:
                    continue
                env_vars[env_var] = env_value
        return env_vars
    
    @staticmethod
    def get_and_convert_env_var(env_var_name):
        env_value = os.getenv(env_var_name.upper())
        env_value = ConfigSharedTools.parse_env_variable(env_value)
        if env_value is None:
            return None
        return env_value
    
    @staticmethod
    def parse_env_variable(env_var):
        if env_var is None:
            return None
        if isinstance(env_var, str):
            env_var = env_var.strip()
            if env_var.startswith("'") and env_var.endswith("'"):
                env_var = env_var[1:-1]
                return ConfigSharedTools.parse_list(env_var)
            elif env_var.startswith('"') and env_var.endswith('"'):
                env_var = env_var[1:-1]
        try:
            # check for integer
            env_var = int(env_var)
            return env_var
        except ValueError:
            try:
                # if not integer, check for float
                env_var = float(env_var)
            except ValueError:
                if env_var.lower() == "none" or env_var == "":
                    return None
                # bool check
                if env_var.lower() in ("yes", "true", "t", "y"):
                    return True
                if env_var.lower() in ("no", "false", "f", "n"):
                    return False
        env_var = ConfigSharedTools.parse_list(env_var)
        # Otherwise it's a a string
        return env_var
       
    @staticmethod
    def parse_list(env_var):
        try:
            maybe_list = ast.literal_eval(env_var)
            if not isinstance(maybe_list, list):
                return env_var
            env_var_list = []
            for split in maybe_list:
                env_var_list.append(ConfigSharedTools.parse_env_variable(split))
            return env_var_list
        except (ValueError, SyntaxError):
            # If a ValueError or SyntaxError is raised, return the original string value
            return env_var
    
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
    
    
 