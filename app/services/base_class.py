import os
from dotenv import load_dotenv


class BaseClass:
    openai_api_key: str = None
    pinecone_api_key: str = None
    index_name: str = None
    index_env: str = None

    _MONIKERS: list = []

    _DEVOPS_VARIABLES: list = [
        "docker_token",
        "stackpath_client_id",
        "stackpath_api_client_secret",
        "docker_username",
        "docker_repo",
    ]
    _SECRET_VARIABLES: list = [
        "docker_token",
        "stackpath_client_id",
        "stackpath_api_client_secret",
        "openai_api_key",
        "pinecone_api_key",
    ]

    def __init__(self):
        # Creates instance variables from class variables
        for k, v in vars(self.__class__).items():
            if not k.startswith("_") and not callable(v):
                setattr(self, k, v)
        self.LoadInstanceVarsFromEnv()

    def LoadInstanceVarsFromEnv(self):
        # Finds the most granular var available for an instance.
        # Starting with the least specific, and overriding if a more specific var exists
        deployment = self.deployment_name.upper()
        moniker = getattr(self, "moniker_name", None)
        class_name = getattr(self, "class_name", None)
        for var, _ in vars(self).items():
            if var.startswith("_") and callable(getattr(self, var)):
                continue
            env_var_name = f"{deployment.upper()}_{var.upper()}"
            env_value = self.get_and_convert_env_vars(env_var_name)
            if env_value is not None:
                setattr(self, var, env_value)
            # Class should not be nameless
            if class_name is not None:
                env_var_name = (
                    f"{deployment.upper()}_{class_name.upper()}_{var.upper()}"
                )
                env_value = self.get_and_convert_env_vars(env_var_name)
                if env_value is not None:
                    setattr(self, var, env_value)
                if moniker is not None:
                    env_var_name = f"{deployment.upper()}_{moniker.upper()}_{class_name.upper()}_{var.upper()}"
                    env_value = self.get_and_convert_env_vars(env_var_name)
                    if env_value is not None:
                        setattr(self, var, env_value)
            if moniker is not None:
                env_var_name = f"{deployment.upper()}_{moniker.upper()}_{var.upper()}"
                env_value = self.get_and_convert_env_vars(env_var_name)
                if env_value is not None:
                    setattr(self, var, env_value)

    def CheckRequiredVars(self, required_vars):
        for var in required_vars:
            if not var.startswith("_") and not callable(getattr(self, var)):
                value = getattr(self, var, None)
                if value is None or value == "":
                    raise ValueError(
                        f"{var} is not set or is an empty string after loading environment variables"
                    )

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

    @classmethod
    def InitialConfigCheck(cls, deployment_name):
        # Initial check to ensure the deployment config is set up for config or deployment
        path = f"app/deployments/{deployment_name}/{deployment_name}_deployment.env"
        load_dotenv(path)
        cls.deployment_name = os.getenv("DEPLOYMENT_NAME")
        if cls.deployment_name is None or cls.deployment_name == "":
            raise ValueError(
                "No deployment found. Try run.py --config 'new deployment name'"
            )
        cls.enabled_monikers = os.getenv(f"{deployment_name.upper()}_ENABLED_MONIKERS")
        cls.enabled_monikers = [
            str(id).strip() for id in cls.enabled_monikers.split(",") if id.strip()
        ]
        if cls.enabled_monikers is None or cls.enabled_monikers == "":
            raise ValueError("No monikers found in deployment.env")
        for moniker_name in cls.enabled_monikers:
            cls._MONIKERS.append(Moniker(moniker_name))


class Moniker(BaseClass):
    moniker_enabled: bool = None
    openai_api_key: str = None
    pinecone_api_key: str = None
    index_name: str = None
    index_env: str = None
    enabled_sprites: str = None
    enabled_data_namespaces: str = None

    def __init__(self, moniker_name):
        self.moniker_name = moniker_name
        super().__init__()
        self.enabled_sprites = [
            str(id).strip() for id in self.enabled_sprites.split(",") if id.strip()
        ]
        self.enabled_data_namespaces = [
            str(id).strip()
            for id in self.enabled_data_namespaces.split(",")
            if id.strip()
        ]
        required_vars = []
        for var in vars(__class__):
            required_vars.append(var)
        self.CheckRequiredVars(required_vars)
