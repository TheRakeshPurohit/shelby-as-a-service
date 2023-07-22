import sys
import argparse
import traceback
from services.base_class import BaseClass
from sprites.discord_sprite import DiscordSprite

def main(args):
    # try: 

        if args.deployment:
            run_deployment()
        elif args.config:
            pass
        elif args.web:
            # Call your web function here.
            pass
        elif args.index:
            # Call your index function here.
            pass
        else:
            raise ValueError("Requires arg")
            
    # except Exception as e:
    #         # Logs error and sends error to sprite
    #         error_info = traceback.format_exc()
    #         print(f'An error occurred in run.py main(): {e}\n{error_info}')
    #         raise

def run_deployment():
    for moniker, sprites in BaseClass.deployment_sprites.items():
        for platform in sprites:
            run_sprite(moniker, platform)
            
def run_sprite(moniker, platform):
    match platform:
        case 'discord':
            DiscordSprite(moniker)
        case _:
            print(f'oops no {platform} of that name')
            

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--deployment', action='store_true', help='Run complete deployment')
    group.add_argument('--config', help='Run config from file')
    group.add_argument('--web', help='Run specific sprite')
    group.add_argument('--index', help='Run specific sprite')
    
    # Manually create args for testing
    # test_args = ['--config', 'app/deploy/test_deployment_config.yaml']
    test_args = ['--deployment']
    args = parser.parse_args(test_args)
    
    # args = parser.parse_args(sys.argv[1:])
    
    main(args)
    

# from sprites.web.web_sprite import WebSprite

# from services.shelby_agent import ShelbyAgent

# from services.index_service import IndexService
# from services.deployment_service import DeploymentService

### Index Managment ###

# def manage_index():
#     agent = IndexAgent()
#     agent.ingest_docs()
#     # agent.delete_index()
#     # agent.clear_index()
#     # agent.clear_namespace('stackpath')

# Remove comment to run index_agent
# manage_index()