import sys

import argparse
from importlib import import_module
from services.deployment_service import DeploymentInstance

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
        help="Run container deployment from specified deployment file.",
    )

    args = parser.parse_args(sys.argv[1:])
    deployment_name = args.run

    config_module_path = f"deployments.{deployment_name}.deployment_config"
    config_module = import_module(config_module_path)
        
    deployment_name = DeploymentInstance(config_module)

main()
