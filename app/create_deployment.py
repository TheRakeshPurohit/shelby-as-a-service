from sprites.discord.discord_sprite import DiscordSprite
from sprites.web.web_sprite import WebSprite
from services.deployment_service import DeploymentService

def run(deployment_config_filename):
    deployment_service = DeploymentService(deployment_config_filename)
    deployment_service.create_deployment()
    
run('app/deploy/personal_deployment_config.yaml')