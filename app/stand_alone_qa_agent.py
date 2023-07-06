import asyncio
import logging
from agents.logger_agent import LoggerAgent
from agents.async_shelby_agent import ShelbyAgent

log_agent = LoggerAgent('qa_agent', 'qa_agent.log', level='INFO')

async def run(request):
    agent = ShelbyAgent()
    response = await agent.run_request(request)
    log_agent.print_and_log(response)

# for testing
# request = "Can you get me information about block 202373690 on solana?"
request = "Can you tell me about what deepgram does and how speach to text can be used?"
# request = "can you tell me how to create a curl and javascript fetch request using the tatum api to fetch the latest block on solana using native rpc client on an rpc node?"

asyncio.run(run(request))
