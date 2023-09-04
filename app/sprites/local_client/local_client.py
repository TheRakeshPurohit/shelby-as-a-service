# region
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import random
import json
import shutil
import gradio as gr
from importlib import import_module
from services.log_service import Logger
from services.deployment_service import DeploymentInstance
from deployment_maker.make import DeploymentMaker
from services.shelby_agent import ShelbyAgent

# endregion


class LocalClientSprite:
    def __init__(self):
        self.log = Logger(
            "local_client",
            "LocalClientSprite",
            f"local_client.md",
            level="INFO",
        )
        self.log.print_and_log_gradio("Starting LocalClientSprite.")

        self.existing_deployment_names = []
        self.deployments_exist = False
        self.load_existing_deployments()
     
        
        with gr.Blocks(title="Deployment Management") as self.loader:
            with gr.Row():
                output_textbox = gr.Textbox(value="Load a deployment to continue.", label="Status")
            with gr.Row():
                load_deployments_dropdown = gr.Dropdown(
                    value=self.existing_deployment_names[0],
                    max_choices=1,
                    choices=self.existing_deployment_names,
                    label="Existing Deployments:",
                )
            with gr.Row():
                load_deployment_btn = gr.Button(value="Load Existing Deployment")
            with gr.Row():
                new_deployment_name = gr.Textbox(
                    label="Enter new deployment name (new_deployment_name):"
                )
            with gr.Row():
                make_deployment_btn = gr.Button(value="Make New Deployment")
            with gr.Row():
                delete_deployments_dropdown = gr.Dropdown(
                    value="Danger!",
                    max_choices=1,
                    choices=self.existing_deployment_names,
                    label="Existig Deployments:",
                )
            with gr.Row():
                delete_deployment_radio = gr.Radio(value="Don't Delete", choices=["Don't Delete", "Check to Confirm Delete"])
            with gr.Row():
                delete_deployment_btn = gr.Button(value="Delete Existing Deployment")
            load_deployment_btn.click(
                fn=self.load_deployment,
                inputs=load_deployments_dropdown,
                outputs=output_textbox
            )
            make_deployment_btn.click(
                fn=self.make_new_deployment,
                inputs=new_deployment_name,
                outputs=[
                    output_textbox,
                    load_deployments_dropdown,
                    delete_deployments_dropdown,
                ],
            )
            delete_deployment_btn.click(
                fn=self.delete_deployment,
                inputs=[delete_deployments_dropdown, delete_deployment_radio],
                outputs=[
                    output_textbox,
                    load_deployments_dropdown,
                    delete_deployments_dropdown,
                    delete_deployment_radio,
                ],
            )

        self.ceqChat = gr.ChatInterface(
            self.yes_man,
            chatbot=gr.Chatbot(height=300),
            textbox=gr.Textbox(
                placeholder="Ask me a yes or no question", container=False, scale=7
            ),
            title="Context Enriched Querying",
            description="Ask Yes Man any question",
            retry_btn=None,
            undo_btn="Delete Previous",
            clear_btn="Clear",
        )

        with gr.Blocks() as self.local_client_gradio_log:
            logs_output = gr.Textbox(default="Logs will appear here...", lines=30)
            self.local_client_gradio_log.load(
                self.gradio_logging, None, logs_output, every=3
            )

        self.local_client = gr.TabbedInterface(
            # theme=gr.themes.Soft(),
            interface_list=[self.loader, self.ceqChat, self.local_client_gradio_log],
            tab_names=["Deployment", "CEQ", "Logs"],
        )

    def load_existing_deployments(self):
        base_dir = "app/deployments"
        exclude_dirs = ["template", "local_client"]
        self.existing_deployment_names = []
        self.deployments_exist = True
        # Iterate over all items in the base_dir that are directories
        for deployment in os.listdir(base_dir):
            deployment_path = os.path.join(base_dir, deployment)
            if deployment not in exclude_dirs and os.path.isdir(deployment_path):
                if "deployment_config.py" in os.listdir(deployment_path):
                    self.existing_deployment_names.append(deployment)

        # If no valid deployments are found
        if not self.existing_deployment_names:
            self.deployments_exist = False
            self.existing_deployment_names = [
                "No existing deployments. Please create one."
            ]

        self.log.print_and_log_gradio(
            f"Found existing deployments: {self.existing_deployment_names}"
        )

    def load_deployment(self, deployment_name):
        # Replace this with whatever processing you need
        if self.deployments_exist is False:
            output_message = "No existing to load deployments. Please create one"
            self.log.print_and_log_gradio(output_message)
            
        config_module_path = f"deployments.{deployment_name}.deployment_config"
        config_module = import_module(config_module_path)
        
        # DeploymentInstance(config_module)
        
        output_message = f"Loaded deployment: {deployment_name}"
        self.log.print_and_log_gradio(output_message)
        
        return output_message

    def make_new_deployment(self, new_deployment_name):
        if len(new_deployment_name) < 1:
            output_message = "Please enter a deployment name"
            self.log.print_and_log_gradio(output_message)
            
        elif new_deployment_name in self.existing_deployment_names:
            output_message = "That deployment already exists. Please delete it first"
            self.log.print_and_log_gradio(output_message)
        else:    
            DeploymentMaker(new_deployment_name)
            self.load_existing_deployments()
            output_message = f" Deployment '{new_deployment_name}' created"
            self.log.print_and_log_gradio(output_message)
            
        return (
            f" Deployment '{new_deployment_name}' created",
            gr.Dropdown.update(value=self.existing_deployment_names[0], choices=self.existing_deployment_names),
            gr.Dropdown.update(value="Danger!", choices=self.existing_deployment_names),
        )

    def delete_deployment(self, delete_deployment_name, delete_deployment_radio):
        if delete_deployment_radio != 'Check to Confirm Delete':
            output_message = "Please check the radio box to confirm delete"
            self.log.print_and_log_gradio(output_message)
        else:

            base_dir = "app/deployments"
            exclude_dirs = ["template", "local_client"]

            deployment_path = os.path.join(base_dir, delete_deployment_name)

            if delete_deployment_name in exclude_dirs:
                output_message = "Can't delete"
                self.log.print_and_log_gradio(output_message)
            elif os.path.exists(deployment_path):
                try:
                    shutil.rmtree(deployment_path)
                    output_message = f"Successfully deleted deployment: '{delete_deployment_name}'"
                    self.log.print_and_log_gradio(output_message)
                except Exception as error:
                    output_message = f"Error deleting deployment: '{delete_deployment_name}'. Error: {str(error)}"
                    self.log.print_and_log_gradio(output_message)
            else:
                output_message = f"Deployment: '{delete_deployment_name}' not found."
                self.log.print_and_log_gradio(output_message)

            self.load_existing_deployments()
            
        return (
            output_message,
            gr.Dropdown.update(value=self.existing_deployment_names[0], choices=self.existing_deployment_names),
            gr.Dropdown.update(value="Danger!", choices=self.existing_deployment_names),
            gr.Radio.update(value = "Don't Delete", choices=["Don't Delete", "Check to Confirm Delete"]),
        )

    def yes_man(self, message, history):
        if message.endswith("?"):
            return "Yes"
        else:
            return "Ask me anything!"

    def gradio_logging(self):
        return self.log.read_logs()

    def run_sprite(self):
        try:
            self.local_client.queue().launch()
        except Exception as error:
            # Logs error and sends error to sprite
            print(f"An error occurred in LocalClientSprite run_sprite(): {error}\n")
            raise

    #     @self.bot.event
    #     async def on_ready():

    #         await channel.send(
    #             self.format_message(
    #                 guild_config.discord_welcome_message,
    #                 self.get_random_animal(),
    #             )
    #         )

    #         self.log.print_and_log(
    #             f"Bot has logged in as {self.bot.user.name} (ID: {self.bot.user.id})"
    #         )
    #         self.log.print_and_log("------")

    #     @self.bot.event
    #     async def on_message(message):
    #         # The bot has four configurations for messages:
    #         # 1st, to only receive messages when it's tagged with @sprite-name
    #         # Or 2nd to auto-respond to all messages that it thinks it can answer
    #         # 3rd, the bot can be in restricted to specific channels
    #         # 4th, the bot can be allowed to respond in all channels (channels can be excluded)

    #         guild_config = await self.find_guild_config(message.guild)
    #         if message.author.id == self.bot.user.id:
    #             # Don't respond to ourselves
    #             return

    #         self.log.print_and_log(
    #             f"""Message received: {message.content}
    #                         Server: {message.guild.name}
    #                         Channel: {message.channel.name}
    #                         From: {message.author.name}
    #                         """
    #         )

    #         # 1st case: bot must be tagged with @sprite-name
    #         if guild_config.discord_manual_requests_enabled:
    #             if not self.bot.user.mentioned_in(message):
    #                 # Tagging required, but bot was not tagged in message
    #                 return
    #         # 2nd case: is  bot auto-responds to all messages that it thinks it can answer
    #         elif guild_config.discord_auto_response_enabled:
    #             # if guild_config.discord_auto_response_cooldown:
    #             #     return
    #             # To implement
    #             pass
    #         # 3rd case: bot restricted to responses in specific channels
    #         if guild_config.discord_specific_channels_enabled:
    #             channel_id = self.message_specific_channels(guild_config, message)
    #             if not channel_id:
    #                 # Message not in specified channels
    #                 return
    #         # 4th case: bot allowed in all channels, excluding some
    #         elif guild_config.discord_all_channels_enabled:
    #             channel_id = self.message_excluded_channels(guild_config, message)
    #             if not channel_id:
    #                 # Message in excluded channel
    #                 return
    #         # Implement auto responses in threads guild_config.discord_auto_respond_in_threads

    #         request = message.content.replace(f"<@{self.bot.user.id}>", "").strip()

    #         # If question is too short
    #         if len(request.split()) < 4:
    #             await message.channel.send(
    #                 self.format_message(
    #                     guild_config.discord_short_message, message.author.id
    #                 )
    #             )
    #             return

    #         # Create thread
    #         thread = await message.create_thread(
    #             name=f"{self.get_random_animal()} {message.author.name}'s request",
    #             auto_archive_duration=60,
    #         )

    #         await thread.send(guild_config.discord_message_start)

    #         moniker_instance = self.find_moniker_instance(message.guild)
    #         shelby_agent = ShelbyAgent(moniker_instance, guild_config)

    #         request_response = await self.run_request(shelby_agent, request)
    #         del shelby_agent

    #         if isinstance(request_response, dict) and "answer_text" in request_response:
    #             # Parse for discord and then respond
    #             parsed_reponse = self.parse_discord_markdown(request_response)
    #             self.log.print_and_log(
    #                 f"Parsed output: {json.dumps(parsed_reponse, indent=4)}"
    #             )
    #             await thread.send(parsed_reponse)
    #             await thread.send(guild_config.discord_message_end)
    #         else:
    #             # If not dict, then consider it an error
    #             await thread.send(request_response)
    #             self.log.print_and_log(f"Error: {request_response})")

    # def parse_discord_markdown(self, request_response):
    #     # Start with the answer text
    #     markdown_string = f"{request_response['answer_text']}\n\n"

    #     # Add the sources header if there are any documents
    #     if request_response["documents"]:
    #         markdown_string += "**Sources:**\n"

    #         # For each document, add a numbered list item with the title and URL
    #         for doc in request_response["documents"]:
    #             markdown_string += (
    #                 f"[{doc['doc_num']}] **{doc['title']}**: <{doc['url']}>\n"
    #             )
    #     else:
    #         markdown_string += "No related documents found.\n"

    #     return markdown_string

    # def get_random_animal(self):
    #     # Very important
    #     animals_txt_path = os.path.join("app/prompt_templates/", "animals.txt")
    #     with open(animals_txt_path, "r") as file:
    #         animals = file.readlines()

    #     return random.choice(animals).strip().lower()

    # def format_message(self, template, var=None):
    #     # Formats messages from premade templates
    #     if var:
    #         return template.format(var)

    #     return template.format()

    # async def run_request(self, shelby_agent, request):
    # # Required to run multiple requests at a time in async
    # with ThreadPoolExecutor() as executor:
    #     loop = asyncio.get_event_loop()
    #     response = await loop.run_in_executor(
    #         executor, shelby_agent.request_thread, request
    #     )
    #     return response
