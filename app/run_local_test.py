import sys
import argparse
from importlib import import_module
from services.deployment_service import DeploymentInstance

def main():
    """
    This script runs shelby-as-a-serice 
        with settings specified via command-line arguments
        or
        manual input

    Arguments:
        --run: Run the main service
        --index_management: Run index_agent with the settings in the index_description.yaml and models.py files.

    Usage:
        python your_script.py --index_management [deployment_name]
        python your_script.py --run [deployment_name]

    If no arguments are passed, the script defaults to: "--run template"
    """

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--index_management", help="Run index_agent."
    )
    group.add_argument(
        "--run",
        help="Run deployment from specified deployment name.",
    )

    # check if any arguments were provided
    if len(sys.argv) == 1:
        ### Add deployment name here if you're too lazy to use the CLI ###
        # test_args = ["--index_management", "template"]
        test_args = ["--run", "template"]
        args = parser.parse_args(test_args)
    else:
        # arguments were provided, parse them
        args = parser.parse_args()

    if args.index_management:
        deployment_name = args.index_management
        run_index_management=True
    elif args.run:
        deployment_name = args.run
        run_index_management=None
        
    config_module_path = f"deployments.{deployment_name}.deployment_config"
    config_module = import_module(config_module_path)
    deployment = DeploymentInstance(config_module, run_index_management)


    ### Right now we don't have index_agent set up for anything but manual input ###

    # Add documents to the vectorstore based on what's enabled in index_description.yaml
    deployment.index_agent.ingest_docs()
    
    # Clears all documents in your vectorstore based on the deployment name (namespace)
    # deployment.index_agent.clear_deplyoment()
    
    # Removes all documents across all deployments
    # deployment.index_agent.clear_index()

main()