import sys
import os
import argparse
import traceback

from deployment_configurator.deployment_instance import DeploymentInstance
from sprites.discord_sprite import DiscordSprite
from services.index_service import IndexService
from deployment_maker.deployment_builder import ConfigTemplateCreator, EnvConfigCreator, WorkflowBuilder

def main(command):
    print(f"Starting deployment with command run.py --{command}")
    try:
        if command.create_template:
            ConfigTemplateCreator(command.create_template).create_template()
        elif command.update_config:
            EnvConfigCreator(command.update_config).update_config()
        elif command.build_workflow:
            WorkflowBuilder(command.build_workflow).build_workflow()
        elif command.index_management:
            run_index_management(command.index_management)
        elif command.container_deployment:
            run_container_deployment(command.container_deployment)
        elif command.local_deployment:
            run_local_deployment(command.local_deployment)

    except Exception as error:
        # Logs error and sends error to sprite
        error_info = traceback.format_exc()
        print(f"An error occurred in run.py main(): {error}\n{error_info}")
        raise

def run_index_management(deployment_name):
    deployment = DeploymentInstance()
    deployment.load_and_check_deployment(deployment_name, run_index_management=True)
    IndexService(deployment).ingest_docs()

            
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
        "--index_management", help="Run index_agent with the settings in the data_classes.py file."
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
    # test_args = ["--local_deployment", "test"]
    # test_args = ["--index_management", "test"]

    # test_args = ['--create_template', 'test']
    # test_args = ['--update_config', 'test']
    # test_args = ['--build_workflow', 'test']

    # args = parser.parse_args(test_args)

    args = parser.parse_args(sys.argv[1:])

    main(args)
