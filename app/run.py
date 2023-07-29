import sys
import os
import argparse
import traceback

from services.classes.deployment_runner import DeploymentClass
from sprites.discord_sprite import DiscordSprite
from services.build.deployment_builder import ConfigTemplateCreator, EnvConfigCreator, WorkflowBuilder

def main(command):
    try:
        if command.create_template:
            ConfigTemplateCreator(command.create_template).create_template()
        elif command.update_config:
            EnvConfigCreator(command.update_config).update_config()
        elif command.build_workflow:
            WorkflowBuilder(command.build_workflow).build_workflow()
        
        
        if command.container_deployment:
            run_container_deployment(command.container_deployment)
        if command.local_deployment:
            run_local_deployment(command.local_deployment)

        # if command.web:
        #     # Call your web function here.
        #     pass
        # if command.index:
        #     # Call your index function here.
        #     pass

    except Exception as error:
        # Logs error and sends error to sprite
        error_info = traceback.format_exc()
        print(f"An error occurred in run.py main(): {error}\n{error_info}")
        raise

def run_container_deployment(deployment_name):
    deployment = DeploymentClass()
    deployment.load_and_check_deployment(deployment_name)
    for moniker in deployment.monikers:
        for sprite in moniker.moniker_enabled_sprite_names:
            run_sprite(sprite)

def run_local_deployment(deployment_name):
    deployment = DeploymentClass()
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
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--container_deployment",
        help="Run container deployment from specified .env file.",
    )
    group.add_argument(
        "--local_deployment", help="Run local deployment from specified .env file."
    )
    group.add_argument(
        "--create_template",
        help="Creates a blank deployment.env and config.yaml from your deployment name.",
    )
    group.add_argument(
        "--update_config", help="Creates or updates deployment.env from config.yaml."
    )
    group.add_argument(
        "--build_workflow",
        help="Creates deployment workflow from deployment.env and config.yaml.",
    )

    # Manually create args for testing
    test_args = ["--local_deployment", "test"]

    # test_args = ['--create_template', 'test']
    # test_args = ['--update_config', 'test']
    # test_args = ['--build_workflow', 'test']

    args = parser.parse_args(test_args)

    # args = parser.parse_args(sys.argv[1:])

    main(args)
