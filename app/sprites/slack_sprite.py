# region
import os, asyncio, random
from concurrent.futures import ThreadPoolExecutor
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from services.log_service import Logger

from services.shelby_agent import ShelbyAgent

# endregion


class SlackSprite:
    def __init__(self, deployment):
        self.log = Logger(
            deployment.deployment_name,
            "discord_sprite",
            f"discord_sprite.md",
            level="INFO",
        )
        self.log.print_and_log("Starting SlackSprite.")
        self.deployment = deployment

        self.bot_user_id = None
        self.app = AsyncApp(token=self.deployment.secrets["slack_bot_token"])

        @self.app.command("/query")
        async def query_command(ack, body):
            await ack()
            user_id = body["user_id"]
            # get channel
            channel = body["channel_id"]
            query = body["text"]
            words = query.split()
            if len(words) < 4:
                # reply invisible to channel
                await ack(
                    f"Hi <@{user_id}>! Brevity is the soul of wit, but not of good queries. Please provide more details in your request."
                )
                return

            moniker_instance = self.find_moniker_instance(body["team_id"])
            if moniker_instance is None:
                self.log.print_and_log(
                    f"Something went wrong loading the team {body['team_id']} for SlackSprite"
                )

            random_animal = await self.get_random_animal()

            # intial reply in channel
            response = await self.app.client.chat_postMessage(
                channel=channel,
                text=(
                    f"{random_animal} <@{user_id}> relax a moment while we fetch your query: `{query}`"
                ),
                unfurl_links=False,
                unfurl_media=False,
            )
            # get reply id
            thread_ts = response["ts"]

            # run query
            shelby_agent = ShelbyAgent(
                moniker_instance, moniker_instance.sprites["SlackSprite"]
            )
            request_response = await self.run_request(shelby_agent, query)
            del shelby_agent

            if isinstance(request_response, dict) and "answer_text" in request_response:
                parsed_output = self.parse_slack_markdown(request_response)
                # use reply itd to reply in thread
                await self.app.client.chat_postMessage(
                    channel=channel,
                    text=f"{parsed_output}",
                    thread_ts=thread_ts,
                    unfurl_links=False,
                    unfurl_media=False,
                )
            else:
                # If not dict, then consider it an error
                await self.app.client.chat_postMessage(
                    channel=channel,
                    text=f"{request_response}",
                    thread_ts=thread_ts,
                    unfurl_links=False,
                    unfurl_media=False,
                )
                # log_agent.print_and_log(f'Error: {request_response})')

        @self.app.command("/help")
        async def help_command(ack):
            await ack(
                "Run queries with the `/query` command.\n"
                "Due to Slack permissions, here's how and where you can access the SaaS bot:\n"
                "• Any public channel: Initiating `/query` or tagging `@shelby-as-a-service`\n"
                "• Private DMs with the bot: Initiating `/query`\n"
                "• Group DMs including the bot: Initiating `/query` or tagging `@shelby-as-a-service`"
            )

        @self.app.event("app_mention")
        async def bot_mention(ack, event):
            await ack()
            user_id = event["user"]
            # get message id
            thread_ts = event["event_ts"]
            # get channel
            channel = event["channel"]
            query = event["text"].replace(f"<@{self.bot_user_id}>", "").strip()
            words = query.split()
            if len(words) < 4:
                # reply in thread
                await self.app.client.chat_postMessage(
                    channel=channel,
                    text=(f"Hi <@{user_id}>! Please create a longer query."),
                    thread_ts=thread_ts,
                    unfurl_links=False,
                    unfurl_media=False,
                )
                return

            moniker_instance = self.find_moniker_instance(event["team"])
            if moniker_instance is None:
                self.log.print_and_log(
                    f"Something went wrong loading the team {event['team']} for SlackSprite"
                )

            random_animal = await self.get_random_animal()

            # intial reply in thread
            await self.app.client.chat_postMessage(
                channel=channel,
                text=(
                    f"{random_animal} <@{user_id}> relax a moment while we fetch your query: `{query}`"
                ),
                thread_ts=thread_ts,
                unfurl_links=False,
                unfurl_media=False,
            )

            # run query
            shelby_agent = ShelbyAgent(
                moniker_instance, moniker_instance.sprites["SlackSprite"]
            )
            request_response = await self.run_request(shelby_agent, query)
            del shelby_agent

            if isinstance(request_response, dict) and "answer_text" in request_response:
                parsed_output = self.parse_slack_markdown(request_response)
                # reply in thread
                await self.app.client.chat_postMessage(
                    channel=channel,
                    text=f"{parsed_output}",
                    thread_ts=thread_ts,
                    unfurl_links=False,
                    unfurl_media=False,
                )
            else:
                # If not dict, then consider it an error
                await self.app.client.chat_postMessage(
                    channel=channel,
                    text=f"{request_response}",
                    thread_ts=thread_ts,
                    unfurl_links=False,
                    unfurl_media=False,
                )
                # log_agent.print_and_log(f'Error: {request_response})')

    def parse_slack_markdown(self, answer_obj):
        # Start with the answer text
        markdown_string = f"{answer_obj['answer_text']}\n\n"

        # Add the sources header if there are any documents
        if answer_obj["documents"]:
            markdown_string += "Sources:\n"

            # For each document, add a numbered list item with the title and URL
            for i, doc in enumerate(answer_obj["documents"], start=1):
                markdown_string += f"{i}. {doc['title']}: <{doc['url']}>\n"
        else:
            markdown_string += "No related documents found.\n"
        markdown_string += "\n Generated with: " + answer_obj["llm"]
        markdown_string += "\n Memory not enabled. Will not respond with knowledge of past or current query."
        markdown_string += "\n Use `/help` for usage details."

        return markdown_string

    async def get_random_animal(self):
        animals_txt_path = os.path.join("app/prompt_templates/", "animals.txt")
        with open(animals_txt_path, "r") as file:
            animals = file.readlines()

        return random.choice(animals).strip().lower()

    def find_moniker_instance(self, team):
        if team:
            for moniker in self.deployment.monikers.values():
                if "SlackSprite" in moniker.sprites:
                    servers = moniker.sprites["SlackSprite"].slack_enabled_teams
                    if team in servers:
                        return moniker

        self.log.print_and_log(f"No matching moniker found for {team}")
        return None

    async def run_request(self, shelby_agent, request):
        # Required to run multiple requests at a time in async
        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                executor, shelby_agent.request_thread, request
            )
            return response

    def run_sprite(self):
        # This function will run in a new thread and start the event loop
        asyncio.run(self.start())

    async def start(self):
        try:
            # Get the bot user ID from auth.test
            handler = AsyncSocketModeHandler(
                app=self.app, app_token=self.deployment.secrets["slack_app_token"]
            )
            response = await self.app.client.auth_test()
            self.bot_user_id = response["user_id"]
            await handler.start_async()
        except Exception as error:
            # Logs error and sends error to sprite
            print(f"An error occurred in DiscordSprite run_discord_sprite(): {error}\n")
            raise
