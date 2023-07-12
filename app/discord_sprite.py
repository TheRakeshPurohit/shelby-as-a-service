#region
import os, random

import discord
from discord.ext import commands

from dotenv import load_dotenv
load_dotenv()

from agents.logger_agent import LoggerAgent
from agents.async_shelby_agent import ShelbyAgent
from configuration.shelby_agent_config import AppConfig

log_agent = LoggerAgent('discord_sprite', 'DiscordSprite.log', level='INFO')
agent_config = AppConfig('discord') 

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents)
#endregion

@bot.event
async def on_guild_join(guild):
    
    # This checks if the specified channel_id exists in the server the bot is added to and leaves if it doesn't exist
    # This prevents the bot from being added to servers that aren't approved
    if not any(channel.id == int(agent_config.discord_channel_id) for channel in guild.channels):
            log_agent.print_and_log(f'Leaving guild {guild.name} (ID: {guild.id}) due to missing channel.')
            await guild.leave()
    channel = bot.get_channel(int(agent_config.discord_channel_id))
    
    await channel.send(format_message(agent_config.discord_welcome_message, get_random_animal()))
            
@bot.event
async def on_ready():
    
    # App start up actions
    for guild in bot.guilds:
        if not any(channel.id == int(agent_config.discord_channel_id) for channel in guild.channels):
            log_agent.print_and_log(f'Leaving guild {guild.name} (ID: {guild.id}) due to missing channel.')
            await guild.leave()
        
    log_agent.print_and_log(f'Bot has logged in as {bot.user.name} (ID: {bot.user.id})')
    log_agent.print_and_log('------')
    channel = bot.get_channel(int(agent_config.discord_channel_id))

    await channel.send(format_message(agent_config.discord_welcome_message, get_random_animal()))

@bot.event
async def on_message(message):
    
    # On messages in the server. The bot should be configured in discord developer portal to only recieve messages where it's tagged,
    # but in the case it's configured to recieve all messages we cover for this case as well
    log_agent.print_and_log(f'Message received: {message.content} (From: {message.author.name})')
    if bot.user.mentioned_in(message):
        # Don't respond to ourselves
        if message.author == bot.user.id:
            return
        if "rabbit" in message.content.lower():
            await message.channel.send(f'No, I will not tell you about the rabbits, <@{message.author.id}>,.')
            return
        # Must be in the approved channel
        if message.channel.id != int(agent_config.discord_channel_id):
            return
        
        request = message.content.replace(f'<@{bot.user.id}>', '').strip()
    
        # If question is too short
        if len(request.split()) < 4:
            await message.channel.send(format_message(agent_config.discord_short_message, message.author.id))
            return
        
        # Create thread
        thread = await message.create_thread(name=f"{get_random_animal()} {message.author.name}'s request", auto_archive_duration=60)

        await thread.send(agent_config.discord_message_start)
        
        request_response = await agent.run_request(request)

        if isinstance(request_response, dict) and 'answer_text' in request_response:
            # Parse for discord and then respond
            parsed_reponse = parse_discord_markdown(request_response)
            await thread.send(parsed_reponse)
            await thread.send(agent_config.discord_message_end)
            log_agent.print_and_log(f'Parsed output: {parsed_reponse})')
        else:
            # If not dict, then consider it an error
            await thread.send(request_response)
            log_agent.print_and_log(f'Error: {request_response})')
        
def parse_discord_markdown(request_response):
    
    # Start with the answer text
    markdown_string = f"{request_response['answer_text']}\n\n"

    # Add the sources header if there are any documents
    if request_response['documents']:
        markdown_string += "**Sources:**\n"

        # For each document, add a numbered list item with the title and URL
        for doc in request_response['documents']:
            markdown_string += f"[{doc['doc_num']}] **{doc['title']}**: <{doc['url']}>\n"
    else:
        markdown_string += "No related documents found.\n"
  
    return markdown_string

def get_random_animal():
    
    # Very important
    animals_txt_path = os.path.join('data', 'animals.txt')
    with open(animals_txt_path, 'r') as file:
        animals = file.readlines()
    
    return random.choice(animals).strip().lower()

def format_message(template, var=None):
    
    # Formats messages from premade templates
    if var:
        return template.format(var)
    
    return template.format

if __name__ == "__main__":
    
    # Runs the bot through the asyncio.run() function built into the library
    agent = ShelbyAgent('discord')
    bot.run(agent_config.discord_token)


