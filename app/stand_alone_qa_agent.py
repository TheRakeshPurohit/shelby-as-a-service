import asyncio
import logging
from logger import setup_logger
from agents.async_shelby_agent import ShelbyAgent

logger = setup_logger('qa_agent', 'qa_agent.log', level=logging.DEBUG)

async def run(query):
    agent = ShelbyAgent()
    response = await agent.run_query(query)
    print(response)

# for testing
query = "can you create a curl and javascript fetch request using the tatum api to fetch the latest block on solana using native rpc client on an rpc node?"

asyncio.run(run(query))
