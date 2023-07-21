from sprites.discord.discord_sprite import DiscordSprite
from sprites.web.web_sprite import WebSprite
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

# def create_deployments():
#     deployment_agent = DeploymentAgent()
#     deployment_agent.generate_deployments()
    
# create_deployments()

def run_discord_sprite():
    DiscordSprite('personal')

# run_discord_sprite()

def run_web_sprite():
    WebSprite('personal')

run_web_sprite()