import sys
import argparse
import traceback
from services.log_service import LogService

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


def main(args):
    try: 
        log_service = LogService('Run', 'Run.log', level='INFO')

        if args.deployment:
            if len(args.deployment) != 3:
                raise ValueError("Deployment argument needs exactly 3 parameters: deployment, moniker, sprite")
            deployment_name, moniker_name, platform = args.deployment
        
        elif args.config:
            from services.deployment_service import DeploymentService
            deployment_service = DeploymentService(args.config, log_service)
            deployment_service.create_deployment_from_file()
        
        elif args.web:
            # Call your web function here.
            pass
        
        elif args.index:
            # Call your index function here.
            pass
        
        else:
            raise ValueError("Requires arg")
            
    except Exception as e:
            # Logs error and sends error to sprite
            error_info = traceback.format_exc()
            log_service.print_and_log(f'An error occurred in run.py main(): {e}\n{error_info}')
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--deployment', nargs=3, help='Run complete deployment: deployment moniker sprite')
    group.add_argument('--config', help='Run config from file')
    group.add_argument('--web', help='Run specific sprite')
    group.add_argument('--index', help='Run specific sprite')
    
    # Manually create args for testing
    test_args = ['--config', 'app/deploy/test_deployment_config.yaml']
    args = parser.parse_args(test_args)
    
    # args = parser.parse_args(sys.argv[1:])
    
    main(args)
    
