import os
import inspect
import concurrent.futures
import yaml
from dotenv import load_dotenv
from sprites.discord_sprite import DiscordSprite
from sprites.slack_sprite import SlackSprite
from services.index_service import IndexService
from models.models import IndexModel


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class DeploymentInstance(metaclass=SingletonMeta):
    def __init__(self, config, run_index_management=None):
        ### Deployment
        self.config = config
        self.deployment_name = config.DeploymentConfig.deployment_name
        self.used_sprites = set()
        self.secrets = {}
        load_dotenv(f"app/deployments/{self.deployment_name}/.env")
        ### Monikers
        self.monikers = {}
        self.load_index()
        for moniker in config.DeploymentConfig.MonikerConfigs.__dict__:
            if not moniker.startswith("_") and not moniker.endswith("_"):
                moniker_config = getattr(
                    config.DeploymentConfig.MonikerConfigs, moniker
                )
                if moniker_config.enabled:
                    self.monikers[moniker] = MonikerInstance(
                        self, moniker_config, moniker
                    )

        if run_index_management:
            self.index_agent = self.load_index_agent()
        else:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                for SpriteClass in self.used_sprites:
                    executor.submit(SpriteClass(self).run_sprite)

    def load_index(self):
        with open(
            f"app/deployments/{self.deployment_name}/index_description.yaml",
            "r",
            encoding="utf-8",
        ) as stream:
            self.index_description_file = yaml.safe_load(stream)

        self.index_data_domains = {}
        # Iterate over each domain in the yaml file
        for domain in self.index_description_file["data_domains"]:
            self.index_data_domains[domain["name"]] = domain["description"]

        self.index_name: str = self.index_description_file["index_name"]
        self.index_env: str = self.index_description_file["index_env"]

    def load_index_agent(self):
        self.index_config = IndexModel()
        for secret in self.index_config.SECRETS_:
            self.secrets[secret] = os.environ.get(
                f"{self.deployment_name.upper()}_{secret.upper()}"
            )
        return IndexService(self)


class MonikerInstance:
    ### We'll create an instance of each monikers required service config as a child of the moniker
    def __init__(self, deployment_instance, moniker_config, moniker_name):
        self.moniker_name = moniker_name
        self.deployment_instance = deployment_instance
        self.enabled: bool = moniker_config.enabled
        self.moniker_data_domains: dict = {}
        for domain in deployment_instance.index_description_file["data_domains"]:
            if domain["name"] in moniker_config.enabled_data_domains:
                self.moniker_data_domains[domain["name"]] = domain["description"]

        # Get enabled sprites
        self.sprites: dict = {}
        for config_name, sprite_config in moniker_config.__dict__.items():
            if inspect.isclass(sprite_config):
                if sprite_config.enabled:
                    sprite_model = self.load_sprite(sprite_config)
                    sprite_name = self.match_sprite(config_name).__name__
                    self.sprites[sprite_name] = sprite_model
                    deployment_instance.used_sprites.add(self.match_sprite(config_name))
                    for secret in sprite_config.model.SECRETS_:
                        deployment_instance.secrets[secret] = os.environ.get(
                            f"{deployment_instance.deployment_name.upper()}_{secret.upper()}"
                        )

    def load_sprite(self, config):
        sprite_model = config.model()
        # Load all var names from SpriteConfig
        config_class_fields = set(
            k
            for k, v in config.__dict__.items()
            if not k.startswith("_") and not k.endswith("_") and not callable(v)
        )
        sprite_model_fields = set(
            k
            for k, v in sprite_model.__dict__.items()
            if not k.startswith("_") and not k.endswith("_") and not callable(v)
        )

        # Accumulate all var names from required_services
        service_model_fields = set()
        for service_model in sprite_model.required_services:
            service_model_fields.update(
                k
                for k, v in service_model.__dict__.items()
                if not k.startswith("_") and not k.endswith("_") and not callable(v)
            )

        # Now go through each field in the combined set of fields
        for field in sprite_model_fields.union(
            config_class_fields, service_model_fields
        ):
            # If the attribute is in SpriteConfig, get the value from there
            if field in config_class_fields and getattr(config, field):
                setattr(sprite_model, field, getattr(config, field))
            # Else get the value from the sprite_model
            elif field in sprite_model_fields and getattr(sprite_model, field):
                continue  # The value is already in sprite_model
            # Else get the value from service_model
            elif field in service_model_fields:
                for service_model in sprite_model.required_services:
                    if hasattr(service_model, field):
                        setattr(sprite_model, field, getattr(service_model, field))
                        break

        return sprite_model

    def match_sprite(self, sprite_name):
        match sprite_name:
            case "DiscordConfig":
                return DiscordSprite
            case "SlackConfig":
                return SlackSprite
            case _:
                print("Error loading sprite!")
