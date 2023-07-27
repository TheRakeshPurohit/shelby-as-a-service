# region
# from services.log_service import LogService
import os
import random
from dataclasses import dataclass, field
import discord
from discord.ext import commands
from services.classes.base import BaseClass
from services.shelby_agent import ShelbyAgent
# endregion


class DiscordSprite(BaseClass):
    def __init__(self, deployment):

        self.deployment = deployment
        
        
        self.intents = discord.Intents.default()
        self.intents.guilds = True
        self.bot = commands.Bot(
            command_prefix=commands.when_mentioned_or("!"), intents=self.intents
        )

        # self.log_service = LogService(f'{moniker}_discord_sprite', f'{moniker}_discord_sprite.log', level='INFO')

        
        @self.bot.event
        async def on_guild_join(guild):
            # Checks the guild server ID in the list of monikers, and returns none if it can't find it
            guild_config = self.find_guild_config(guild)
            if guild_config is None:
                await guild.leave()
            channel = self.channel_join_ready(guild_config, guild)
            if channel:
                await channel.send(
                    self.format_message(guild_config.get('discord_welcome_message'), self.get_random_animal())
                )

        @self.bot.event
        async def on_ready():
            # App start up actions
            for guild in self.bot.guilds:
                guild_config = self.find_guild_config(guild)
                if guild_config is None:
                    await guild.leave()
                channel = self.channel_join_ready(guild_config, guild)
                if channel:
                    await channel.send(
                        self.format_message(guild_config.get('discord_welcome_message'), self.get_random_animal())
                    )

            # self.log_service.print_and_log(f'Bot has logged in as {self.bot.user.name} (ID: {self.bot.user.id})')
            # self.log_service.print_and_log('------')

        @self.bot.event
        async def on_message(message):
            # The bot has four configurations for messages:
            # 1st, to only receive messages when it's tagged with @sprite-name
            # Or 2nd to auto-respond to all messages that it thinks it can answer
            # 3rd, the bot can be in restricted to specific channels 
            # 4th, the bot can be allowed to respond in all channels (channels can be excluded)
            
            # self.log_service.print_and_log(f'Message received: {message.content} (From: {message.author.name})')
            
            guild_config = self.find_guild_config(message.guild)
            if guild_config is None:
                await message.guild.leave()
                return
                    
            if message.author == self.bot.user.id:
                # Don't respond to ourselves
                return
            
            # 1st case: bot must be tagged with @sprite-name
            if guild_config.get('discord_manual_requests_enabled'):
                if not self.bot.user.mentioned_in(message):
                    # Tagging required, but bot was not tagged in message
                    return
            # 2nd case: is  bot auto-responds to all messages that it thinks it can answer
            elif guild_config.get('discord_auto_response_enabled'):
                # if guild_config.discord_auto_response_cooldown:
                #     return
                # To implement
                pass
            # 3rd case: bot restricted to responses in specific channels
            if guild_config.get('discord_specific_channels_enabled'):
                channel_id = self.message_specific_channels(guild_config, message)
                if not channel_id:
                    # Message not in specified channels
                    return
            # 4th case: bot allowed in all channels, excluding some
            elif guild_config.get('discord_all_channels_enabled'):
                channel_id = self.message_excluded_channels(guild_config, message)
                if not channel_id:
                    # Message in excluded channel
                    return
            # Implement auto responses in threads guild_config.discord_auto_respond_in_threads
            
            request = message.content.replace(f"<@{self.bot.user.id}>", "").strip()

            # If question is too short
            if len(request.split()) < 4:
                await message.channel.send(
                    self.format_message(guild_config.get('discord_short_message'), message.author.id)
                )
                return

            # Create thread
            thread = await message.create_thread(
                name=f"{self.get_random_animal()} {message.author.name}'s request",
                auto_archive_duration=60,
            )

            await thread.send(guild_config.get('discord_message_start'))
            
            shelby_agent = ShelbyAgent(guild_config)
            request_response = await shelby_agent.run_request(request)
            del shelby_agent

            if (
                isinstance(request_response, dict)
                and "answer_text" in request_response
            ):
                # Parse for discord and then respond
                parsed_reponse = self.parse_discord_markdown(request_response)
                await thread.send(parsed_reponse)
                await thread.send(guild_config.get('discord_message_end'))
                # self.log_service.print_and_log(f'Parsed output: {parsed_reponse})')
            else:
                # If not dict, then consider it an error
                await thread.send(request_response)
                # self.log_service.print_and_log(f'Error: {request_response})')

    def parse_discord_markdown(self, request_response):
        # Start with the answer text
        markdown_string = f"{request_response['answer_text']}\n\n"

        # Add the sources header if there are any documents
        if request_response["documents"]:
            markdown_string += "**Sources:**\n"

            # For each document, add a numbered list item with the title and URL
            for doc in request_response["documents"]:
                markdown_string += (
                    f"[{doc['doc_num']}] **{doc['title']}**: <{doc['url']}>\n"
                )
        else:
            markdown_string += "No related documents found.\n"

        return markdown_string

    def get_random_animal(self):
        # Very important
        animals_txt_path = os.path.join("app/prompt_templates/", "animals.txt")
        with open(animals_txt_path, "r") as file:
            animals = file.readlines()

        return random.choice(animals).strip().lower()

    def format_message(self, template, var=None):
        # Formats messages from premade templates
        if var:
            return template.format(var)

        return template.format()

    def message_specific_channels(self, guild_config, message):
        for config_channel_id in guild_config.get('discord_specific_channel_ids'):
            if message.channel.id == int(config_channel_id):
                return message.channel.id
        return None
    
    def message_excluded_channels(self, guild_config, message):
        for config_channel_id in guild_config.get('discord_all_channels_excluded_channels'):
            if message.channel.id == int(config_channel_id):
                return None
        return message.channel.id

    def find_guild_config(self, guild):
        if guild:
            for moniker in self.deployment.monikers.values():
                if 'discord' in moniker.enabled_sprite_names:
                    servers = moniker.discord_config.get('discord_enabled_servers')
                    if servers and guild.id in servers:
                        return moniker.discord_config

        print(f"No matching discord config found for guild: {guild}")
        return None
    
    def channel_join_ready(self, guild_config, guild):
            # If specific channels enabled, find one that is named 'general' or any approved channel
            matching_channel = None
            if guild_config.get('discord_specific_channels_enabled') and guild_config.get('discord_specific_channel_ids') is not None:
                for channel in guild.channels:
                    for config_channel_id in guild_config.get('discord_specific_channel_ids'):
                        if channel.id == int(config_channel_id):
                            if isinstance(channel, discord.TextChannel) and channel.name == 'general':
                                return channel
                            matching_channel = channel
                return matching_channel
            
            # Otherwise try to return 'general', and return None if we can't.
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) and channel.name == 'general':
                    return channel.id
            # In the future we can say hi in the last channel we spoke in
            return None
    
    def run_discord_sprite(self):
        self.bot.run(self.deployment.discord_bot_token)