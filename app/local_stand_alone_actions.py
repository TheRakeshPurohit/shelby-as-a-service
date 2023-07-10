import asyncio
from agents.logger_agent import LoggerAgent
from agents.async_shelby_agent import ShelbyAgent
from agents.index_agent import IndexAgent


log_agent = LoggerAgent('qa_agent', 'qa_agent.log', level='INFO')

async def run_shelby_agent(request):
    deployment_target = 'discord'
    agent = ShelbyAgent(deployment_target)
    response = await agent.run_request(request)
    log_agent.print_and_log(response)
    
def manage_index():
    agent = IndexAgent()
    agent.ingest_docs()
    # agent.delete_index()
    # agent.clear_index()
    # agent.clear_namespace('')

# manage_index()

# For locally testing shelby_agent 
# request = "Can you get me information about block 202373690 on solana?"
request = "Can you tell me about what deepgram does and how speach to text can be used?"
# request = "Can you tell me about what elephants?"
# request = "can you tell me how to create a curl and javascript fetch request using the tatum api to fetch the latest block on solana using native rpc client on an rpc node?"

asyncio.run(run_shelby_agent(request))
