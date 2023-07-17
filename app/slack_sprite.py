#region
import os, asyncio, random

from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from dotenv import load_dotenv
load_dotenv()

from agents.logger_agent import LoggerAgent
from agents.async_shelby_agent import ShelbyAgent
from configuration.shelby_agent_config import AppConfig
 
agent_config = AppConfig('slack') 
log_agent = LoggerAgent('slack_sprite', 'SlackSprite.log', level='INFO')

bot_user_id = None
app = AsyncApp(token=agent_config.slack_bot_token)
message_start = "Relax and vibe while your query is embedded, documents are fetched, and the LLM is prompted."
#endregion


@app.command("/query")
async def query_command(ack, body):
        
    user_id = body["user_id"]
    # get channel
    channel = body['channel_id']
    query = body["text"]
    words = query.split()
    if len(words) < 4:
        # reply invisible to channel
        await ack(f"Hi <@{user_id}>! Brevity is the soul of wit, but not of good queries. Please provide more details in your request.")
        return
    
    await ack()
    random_animal = await get_random_animal()

    # intial reply in channel
    response = await app.client.chat_postMessage(
        channel=channel, 
        text=(f"{random_animal} <@{user_id}> relax a moment while we fetch your query: `{query}`"), 
        unfurl_links=False,
        unfurl_media=False
    )
    # get reply id 
    thread_ts = response['ts']

    # run query
    request_response = await agent.run_request(query)
    
    if isinstance(request_response, dict) and 'answer_text' in request_response:
        parsed_output = parse_slack_markdown(request_response)
        # use reply itd to reply in thread
        await app.client.chat_postMessage(
            channel=channel, 
            text=f"{parsed_output}", 
            thread_ts=thread_ts, 
            unfurl_links=False,
            unfurl_media=False
        )
    else:
        # If not dict, then consider it an error
        await app.client.chat_postMessage(
            channel=channel, 
            text=f"{request_response}", 
            thread_ts=thread_ts, 
            unfurl_links=False,
            unfurl_media=False
        )
        log_agent.print_and_log(f'Error: {request_response})')

@app.command("/help")
async def help_command(ack):

    await ack("Run queries with the `/query` command.\n"
        "Due to Slack permissions, here's how and where you can access the SaaS bot:\n"
        "• Any public channel: Initiating `/query` or tagging `@shelby-as-a-service`\n"
        "• Private DMs with the bot: Initiating `/query`\n"
        "• Group DMs including the bot: Initiating `/query` or tagging `@shelby-as-a-service`"
    )

@app.event("app_mention")
async def bot_mention(ack, event):
    
    global bot_user_id
    await ack()
    user_id = event["user"]
    # get message id
    thread_ts = event['event_ts']
    # get channel
    channel = event['channel']
    query = event["text"].replace(f'<@{bot_user_id}>', '').strip()
    words = query.split()
    if len(words) < 4:
        # reply in thread
        await app.client.chat_postMessage(
        channel=channel, 
        text=(f"Hi <@{user_id}>! Please create a longer query."), 
        thread_ts=thread_ts, 
        unfurl_links=False,
        unfurl_media=False
        )
        return

    random_animal = await get_random_animal()

    # intial reply in thread
    await app.client.chat_postMessage(
        channel=channel, 
        text=(f"{random_animal} <@{user_id}> relax a moment while we fetch your query: `{query}`"), 
        thread_ts=thread_ts, 
        unfurl_links=False,
        unfurl_media=False
    )
    
    # run query
    request_response = await agent.run_request(query)
    
    if isinstance(request_response, dict) and 'answer_text' in request_response:
        parsed_output = parse_slack_markdown(request_response)
        # reply in thread
        await app.client.chat_postMessage(
            channel=channel, 
            text=f"{parsed_output}", 
            thread_ts=thread_ts, 
            unfurl_links=False,
            unfurl_media=False
        )
    else:
        # If not dict, then consider it an error
        await app.client.chat_postMessage(
            channel=channel, 
            text=f"{request_response}", 
            thread_ts=thread_ts, 
            unfurl_links=False,
            unfurl_media=False
        )
        log_agent.print_and_log(f'Error: {request_response})')

def parse_slack_markdown(answer_obj):
    
    # Start with the answer text
    markdown_string = f"{answer_obj['answer_text']}\n\n"

    # Add the sources header if there are any documents
    if answer_obj['documents']:
        markdown_string += "Sources:\n"

        # For each document, add a numbered list item with the title and URL
        for i, doc in enumerate(answer_obj['documents'], start=1):
            markdown_string += f"{i}. {doc['title']}: <{doc['url']}>\n"
    else:
        markdown_string += "No related documents found.\n"
    markdown_string += "\n Generated with: " + answer_obj['llm']
    markdown_string += "\n Memory not enabled. Will not respond with knowledge of past or current query."
    markdown_string += "\n Use `/help` for usage details."
    
    return markdown_string

async def get_random_animal():
    
    animals_txt_path = os.path.join('app/prompt_templates/', 'animals.txt')
    with open(animals_txt_path, 'r') as file:
        animals = file.readlines()
    
    return random.choice(animals).strip().lower()

async def main():
    
    global bot_user_id
    handler = AsyncSocketModeHandler(app, os.environ.get('SLACK_APP_TOKEN'))
    # Use the client attribute to call auth.test
    response = await app.client.auth_test()
    
    # Get the bot user ID from the response
    bot_user_id = response["user_id"]
    await handler.start_async()

if __name__ == "__main__":
    
    agent = ShelbyAgent('slack')
    asyncio.run(main())
    