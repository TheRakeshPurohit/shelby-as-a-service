import sys

import argparse
from importlib import import_module
from services.deployment_service import DeploymentInstance

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument(
    "--run",
    help="Run container deployment from specified deployment file.",
)
group.add_argument(
    "--run_local_deployment",
    help="Run local deployment from specified deployment file.",
)
# args = parser.parse_args(sys.argv[1:])

test_args = ["--run", "template"]
args = parser.parse_args(test_args)

if args.run:
    deployment_name = args.run
elif args.run_local_deployment:
    deployment_name = args.run_local_deployment

config_module_path = f"deployments.{deployment_name}.deployment_config"
config_module = import_module(config_module_path)

deployment_name = DeploymentInstance(config_module)


        


# deployment_name.load_and_check_deployment(deployment_name)
# for _, moniker_instance in deployment_name.monikers.items():
#     for sprite in moniker_instance.moniker_enabled_sprite_names:
#         match sprite:
#             case "discord":
#                 DiscordSprite(deployment_name).run_discord_sprite()
#             # case "slack":
#             #     SlackSprite().run_slack_sprite()
#             case _:
#                 print(f"oops no {sprite} of that name")
