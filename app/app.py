import sys
import argparse
import traceback
from pathlib import Path
from importlib import import_module
from models.deployment_instance import DeploymentInstance
from sprites.discord_sprite import DiscordSprite

def run(deployment)
    deployment = DeploymentInstance()
    deployment.load_and_check_deployment(deployment)
    for _, moniker_instance in deployment.monikers.items():
        for sprite in moniker_instance.moniker_enabled_sprite_names: 
            match sprite:
                case "discord":
                    DiscordSprite(deployment).run_discord_sprite()
                # case "slack":
                #     SlackSprite().run_slack_sprite()
                case _:
                    print(f"oops no {sprite} of that name")

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument(
    "--run",
    help="Run container deployment from specified deployment file.",
)
group.add_argument(
    "--run_local_deployment", help="Run local deployment from specified deployment file."
)
# args = parser.parse_args(sys.argv[1:])

test_args = ['--run', 'deployment_test']

args = parser.parse_args(test_args)
    
if args.run:
    deployment_name = args.run
elif args.run_local_deployment:
    deployment_name = args.run_local_deployment
    
config_module_path = f"deployments.{deployment_name}.config"
config_module = import_module(config_module_path)

settings = config_module.Settings()

run(deployment_name)
