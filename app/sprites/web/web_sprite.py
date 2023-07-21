#region
import asyncio
from services.log_service import LogService
from sprites.web.web_sprite_config import WebSpriteConfig
from services.shelby_agent import ShelbyAgent
#endregion

class WebSprite:
    def __init__(self, moniker):
        self.log_service = LogService(f'{moniker}_web_sprite', f'{moniker}_web_sprite.log', level='INFO')
        self.config = WebSpriteConfig(moniker, self.log_service) 
        self.shelby_agent = ShelbyAgent(moniker, self.config.platform)
        
        # request = "How can I get the latest block on the Solana blockchain?"
        request = "tell me about nfts and minting them on solana using tatum"
        # request = "Can you tell me about what deepgram does and how speach to text can be used?"
        # request = "Can you show me how to deploy a container workload with a stackpath api request?"
        # request = "Can you tell me about what elephants?"
        # request = "can you tell me how to create a curl and javascript fetch request using the tatum api to fetch the latest block on solana using native rpc client on an rpc node?"

        # Remove comment to run shelby_agent
        asyncio.run(self.run_shelby_agent(request))
        
    async def run_shelby_agent(self, request):
        await self.shelby_agent.run_request(request)