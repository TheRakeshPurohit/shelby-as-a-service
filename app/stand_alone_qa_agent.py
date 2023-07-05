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
# query = "Can you get me information about block 202373690 on solana?"
query = "Can you tell me about what deepgram does and how speach to text can be used?"
# query = "can you tell me how to create a curl and javascript fetch request using the tatum api to fetch the latest block on solana using native rpc client on an rpc node?"

asyncio.run(run(query))
