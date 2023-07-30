import sys
import argparse
import traceback

from deployment_configurator.deployment_instance import DeploymentInstance
from sprites.discord_sprite import DiscordSprite

def main(command):
    print(f"Starting deployment with command run.py --{command}")
    try:
        if command.container_deployment:
            run_container_deployment(command.container_deployment)
        elif command.local_deployment:
            run_local_deployment(command.local_deployment)

    except Exception as error:
        # Logs error and sends error to sprite
        error_info = traceback.format_exc()
        print(f"An error occurred in run.py main(): {error}\n{error_info}")
        raise

def run_container_deployment(deployment_name):
    deployment = DeploymentInstance()
    deployment.load_and_check_deployment(deployment_name)
    for _, moniker_instance in deployment.monikers.items():
        for sprite in moniker_instance.moniker_enabled_sprite_names: 
            match sprite:
                case "discord":
                    DiscordSprite(deployment).run_discord_sprite()
                case "slack":
                    SlackSprite().run_slack_sprite()
                case _:
                    print(f"oops no {sprite} of that name")

def run_local_deployment(deployment_name):
    deployment = DeploymentInstance()
    deployment.load_and_check_deployment(deployment_name)
    for _, moniker_instance in deployment.monikers.items():
        for sprite in moniker_instance.moniker_enabled_sprite_names: 
            match sprite:
                case "discord":
                    DiscordSprite(deployment).run_discord_sprite()
                case "slack":
                    SlackSprite().run_slack_sprite()
                case _:
                    print(f"oops no {sprite} of that name")

if __name__ == "__main__":
    print(f"Starting deployment with deployment_runner.py")
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--container_deployment",
        help="Run container deployment from specified .env file.",
    )
    group.add_argument(
        "--local_deployment", help="Run local deployment from specified .env file."
    )
    # Manually create args for testing
    # test_args = ["--local_deployment", "test"]
    # args = parser.parse_args(test_args)
    args = parser.parse_args(sys.argv[1:])

    main(args)
