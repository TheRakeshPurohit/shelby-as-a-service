import sys
import argparse
from importlib import import_module
from services.deployment_service import DeploymentInstance
from deployment_maker import deploy_stackpath_container


def main():
    """
    This script runs shelby-as-a-serice when deployed to a container.

    Usage:
        None. Deployment will be configured via automation.
    """

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--run",
        help="This will be called from the dockerfile after the container deploys.",
    )
    group.add_argument(
        "--deploy_container",
        help="This will be called from the github actions workflow to deploy the container.",
    )

    args = parser.parse_args(sys.argv[1:])
    if args.run:
        deployment_name = args.run
        config_module_path = f"deployments.{deployment_name}.deployment_config"
        config_module = import_module(config_module_path)
        DeploymentInstance(config_module)
    elif args.deploy_container:
        deployment_name = args.deploy_container
        deploy_stackpath_container.main(deployment_name)


main()
