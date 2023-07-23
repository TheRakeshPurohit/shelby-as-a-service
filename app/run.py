import sys
import os
import argparse
import traceback
from services.base_class import BaseClass
from sprites.discord_sprite import DiscordSprite
from services.deployment_service import ConfigBuilder, DeploymentService


def main(args):
    try: 
        if args.create_config:
            ConfigBuilder(args.create_config.strip()).create_config()
        elif args.create_template:
            ConfigBuilder(args.create_template.strip()).create_template()
        # elif args.create_deployment:
        #     DeploymentService(args.create_deployment.strip()).create_deployment_from_file()
            
        elif args.container_deployment:
            run_container_deployment(args.container_deployment.strip())
        elif args.local_deployment:
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
        print(f'An error occurred in run.py main(): {error}\n{error_info}')
        raise

def run_container_deployment(deployment_name):
    BaseClass.InitialConfigCheck(deployment_name)
    for moniker, sprites in BaseClass.deployment_monikers_sprites.items():
        for platform in sprites:
            run_sprite(moniker, platform)
            
def run_local_deployment(deployment_name):
    path = f'app/deployments/{deployment_name}/{deployment_name}.env'
    BaseClass.InitialConfigCheck(deployment_name, path)
    for moniker, sprites in BaseClass.deployment_monikers_sprites.items():
        for platform in sprites:
            run_sprite(moniker, platform)
            
def run_sprite(moniker, platform):
    match platform:
        case 'discord':
            DiscordSprite(moniker).run_discord_sprite()
        case _:
            print(f'oops no {platform} of that name')
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--container_deployment', help='Run container deployment from specified .env file.')
    group.add_argument('--local_deployment', help='Run local deployment from specified .env file.')
    group.add_argument('--create_config', help='Creates an initial config from your deployment name.')
    group.add_argument('--create_deployment', help='Create a final deployment workflow from your deployment name.')
    group.add_argument('--create_template', help='Creates a .env template to be populated.')

    # Manually create args for testing
    test_args = ['--local_deployment', 'test']
    # test_args = ['--create_config', 'test123']
    # test_args = ['--create_template', 'test123']
    # test_args = ['--create_deployment', 'test']

    args = parser.parse_args(test_args)
    
    # args = parser.parse_args(sys.argv[1:])
    
    main(args)
    

