# region
# from services.log_service import LogService
import os
import random
from dataclasses import dataclass, field
import discord
from discord.ext import commands
from services.base_class import BaseClass, DeploymentClass
from services.shelby_agent import ShelbyAgent
# endregion


class DiscordSprite(BaseClass):
    def __init__(self):

        self.intents = discord.Intents.default()
        self.intents.guilds = True
        self.bot = commands.Bot(
            command_prefix=commands.when_mentioned_or("!"), intents=self.intents
        )
        DeploymentClass
        self.config = DiscordConfig()
        
        
        self.shelby_agent = ShelbyAgent()
        # self.log_service = LogService(f'{moniker}_discord_sprite', f'{moniker}_discord_sprite.log', level='INFO')

    def run_discord_sprite(self):
        @self.bot.event
        async def on_guild_join(guild):
            channel = await check_server_for_channel_id(guild)
            if channel:
                await channel.send(
                    format_message(self.discord_welcome_message, get_random_animal())
                )

        @self.bot.event
        async def on_ready():
            # App start up actions
            for guild in self.bot.guilds:
                channel = await check_server_for_channel_id(guild)
                if channel:
                    await channel.send(
                        format_message(
                            self.discord_welcome_message, get_random_animal()
                        )
                    )

            # self.log_service.print_and_log(f'Bot has logged in as {self.bot.user.name} (ID: {self.bot.user.id})')
            # self.log_service.print_and_log('------')

        @self.bot.event
        async def on_message(message):
            # On messages in the server. The bot should be configured in discord developer portal to only recieve messages where it's tagged,
            # but in the case it's configured to receive all messages we cover for this case as well
            # self.log_service.print_and_log(f'Message received: {message.content} (From: {message.author.name})')
            if self.bot.user.mentioned_in(message):
                # Don't respond to ourselves
                if message.author == self.bot.user.id:
                    return
                if "rabbit" in message.content.lower():
                    await message.channel.send(
                        f"No, I will not tell you about the rabbits, <@{message.author.id}>,."
                    )
                    return
                # Must be in the approved channel
                channel_id = await check_message_for_channel_id(message)
                if not channel_id:
                    return

                request = message.content.replace(f"<@{self.bot.user.id}>", "").strip()

                # If question is too short
                if len(request.split()) < 4:
                    await message.channel.send(
                        format_message(self.discord_short_message, message.author.id)
                    )
                    return

                # Create thread
                thread = await message.create_thread(
                    name=f"{get_random_animal()} {message.author.name}'s request",
                    auto_archive_duration=60,
                )

                await thread.send(self.discord_message_start)

                request_response = await self.shelby_agent.run_request(request)

                if (
                    isinstance(request_response, dict)
                    and "answer_text" in request_response
                ):
                    # Parse for discord and then respond
                    parsed_reponse = parse_discord_markdown(request_response)
                    await thread.send(parsed_reponse)
                    await thread.send(self.discord_message_end)
                    # self.log_service.print_and_log(f'Parsed output: {parsed_reponse})')
                else:
                    # If not dict, then consider it an error
                    await thread.send(request_response)
                    # self.log_service.print_and_log(f'Error: {request_response})')

        def parse_discord_markdown(request_response):
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

        def get_random_animal():
            # Very important
            animals_txt_path = os.path.join("app/prompt_templates/", "animals.txt")
            with open(animals_txt_path, "r") as file:
                animals = file.readlines()

            return random.choice(animals).strip().lower()

        def format_message(template, var=None):
            # Formats messages from premade templates
            if var:
                return template.format(var)

            return template.format

        async def check_server_for_channel_id(guild):
            # This checks if the specified channel_id exists in the server the bot is added to and leaves if it doesn't exist
            # This prevents the bot from being added to servers that aren't approved

            # Initialize a variable to store the matching channel ID
            matching_channel_id = None

            # Check each channel ID in the self.discord_specific_channel_ids list
            for config_channel_id in self.discord_specific_channel_ids:
                # Convert the config_channel_id to an integer
                config_channel_id = int(config_channel_id)

                # Check if the config_channel_id is in the guild's channels
                if any(channel.id == config_channel_id for channel in guild.channels):
                    matching_channel_id = config_channel_id
                    break  # Exit the loop when we find a match

            # If we didn't find a matching channel ID, leave the guild
            if matching_channel_id is None:
                # self.log_service.print_and_log(f'Leaving guild {guild.name} (ID: {guild.id}) due to missing channel.')
                await guild.leave()

                return None
            else:
                # If we found a matching channel ID, get the channel
                channel = self.bot.get_channel(matching_channel_id)

                return channel

        async def check_message_for_channel_id(message):
            # Initialize a variable to store the matching channel ID
            matching_channel_id = None

            # Check each channel ID in the self.discord_specific_channel_ids list
            for config_channel_id in self.discord_specific_channel_ids:
                # Convert the config_channel_id to an integer
                config_channel_id = int(config_channel_id)

                # Check if the config_channel_id is in the guild's channels
                if message.channel.id == config_channel_id:
                    matching_channel_id = config_channel_id
                    break  # Exit the loop when we find a match

            # If we didn't find a matching channel ID, leave the guild
            if matching_channel_id is None:
                return None
            else:
                return matching_channel_id

        # def identify_moniker():
            
        #     return moniker

        self.bot.run(self.discord_bot_token)

@dataclass
class DiscordConfig(BaseClass):
    ### These will all be set by file ###
    discord_enabled_servers: list[int] = None
    discord_manual_requests_enabled: bool = True 
    discord_auto_response_enabled: bool = False
    discord_auto_response_cooldown: int = 10
    discord_auto_respond_in_threads: bool = False 
    discord_all_channels_enabled: bool = False
    discord_all_channels_excluded_channels: list[int] = None
    discord_specific_channels_enabled: bool = True 
    discord_specific_channel_ids: list[int] = None
    discord_user_daily_token_limit: int = 30000
    discord_welcome_message: str = 'ima tell you about the {}.'
    discord_short_message: str = '<@{}>, brevity is the soul of wit, but not of good queries. Please provide more details in your request.'
    discord_message_start: str = 'Running request... relax, chill, and vibe a minute.'
    discord_message_end: str = 'Generated by: gpt-4. Memory not enabled. Has no knowledge of past or current queries. For code see https://github.com/ShelbyJenkins/shelby-as-a-service.'
    discord_bot_token: str = None
    _SECRET_VARIABLES: list = field(default_factory=lambda: [
        "discord_bot_token"
    ])
    required_vars: list = field(default_factory=list)
    
    def load_class_config(self):
        try:
            self.discord_all_channels_excluded_channels = [int(id.strip()) for id in self.discord_enabled_servers.split(",") if id.strip()]
            self.discord_specific_channel_ids = [int(id.strip()) for id in self.discord_enabled_servers.split(",") if id.strip()]
            self.discord_enabled_servers = [int(id.strip()) for id in self.discord_enabled_servers.split(",") if id.strip()]
            self.discord_welcome_message = self.discord_welcome_message.strip('"')
            self.discord_short_message = self.discord_short_message.strip('"')
            self.discord_message_start = self.discord_message_start.strip('"')
            self.discord_message_end = self.discord_message_end.strip('"')
        except AttributeError:
            pass

        if self.discord_manual_requests_enabled is False and self.discord_auto_response_enabled is False:
            raise ValueError(
                "Error: manual_requests_enabled and auto_response_enabled cannot both be False."
            )
        if (self.discord_all_channels_enabled or self.discord_specific_channels_enabled is not None) and \
            self.discord_all_channels_enabled == self.discord_specific_channels_enabled:
            raise ValueError(
                "Error: all_channels_enabled and specific_channels_enabled cannot have the same boolean state."
            )
            
    def check_class_config(self):
        for var in vars(self):
            if not var.startswith("_") and not callable(getattr(self, var)):
                if (var == "discord_all_channels_excluded_channels" and self.discord_all_channels_enabled == False):
                    continue
                if (var == "discord_specific_channel_ids" and self.discord_specific_channels_enabled == False):
                    continue
            self.required_vars.append(var)
            
        BaseClass.check_required_vars(self)