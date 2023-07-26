import sys
import os
import argparse
import traceback
from sprites.discord_sprite import DiscordSprite
from sprites.slack_sprite import SlackSprite
from services.deployment.deployment_service import (
    ConfigTemplate,
    ConfigCreator,
    WorkflowBuilder,
)
from services.base_class import DeploymentClass


def main(args):
    try:
        if args.create_template:
            ConfigTemplate(args.create_template.strip()).create_template()
        elif args.update_config:
            ConfigCreator(args.update_config.strip()).update_config()
        elif args.build_workflow:
            WorkflowBuilder(args.build_workflow.strip()).build_workflow()
        
        
        if args.container_deployment:
            run_container_deployment(args.container_deployment.strip())
        if args.local_deployment:
            run_local_deployment(args.local_deployment.strip())

        elif args.web:
            # Call your web function here.
            pass
        elif args.index:
            # Call your index function here.
            pass

    except Exception as error:
        # Logs error and sends error to sprite
        error_info = traceback.format_exc()
        print(f"An error occurred in run.py main(): {error}\n{error_info}")
        raise


def run_container_deployment(deployment_name):
    deployment = DeploymentClass()
    deployment.load_and_check_deployment(deployment_name)
    for moniker in deployment.monikers:
        for sprite in moniker.enabled_sprites:
            run_sprite(sprite)


def run_local_deployment(deployment_name):
    deployment = DeploymentClass()
    deployment.load_and_check_deployment(deployment_name)
    for _, moniker_instance in deployment.monikers.items():
        for sprite in moniker_instance.enabled_sprites: 
            run_sprite(sprite)


def run_sprite(sprite):
    match sprite:
        case "discord":
            DiscordSprite().run_discord_sprite()
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
