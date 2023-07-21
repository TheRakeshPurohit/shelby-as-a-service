import os
import json, yaml

from dotenv import load_dotenv

# Set your services in the YourConfig class. These are used to automatically create the github action workflows

class ConfigService():
    def __init__(self):
        pass
    ### Running a sprite ###
    def load_env_config(self, generic_config, log_service):
        load_dotenv()
        required_vars_dict: dict = self.add_vars_to_dict(generic_config)
        required_consts_dict: dict = self.load_vars_from_env(generic_config, required_vars_dict)
        self.set_and_check(required_consts_dict, generic_config, log_service)
    
    def add_vars_to_dict(self, generic_config) -> dict:
        required_vars_dict: dict = {}
        for var, value in vars(generic_config).items():
            if not var.startswith('_'):
                required_vars_dict[var] = value

        return  required_vars_dict
        
    def load_vars_from_env(self, generic_config, required_vars_dict) -> dict: 
        required_consts_dict: dict = {}
        for required_var, value in required_vars_dict.items():
            env_value = os.getenv(f'{generic_config.moniker.upper()}_{generic_config.platform.upper()}_{required_var.upper()}')
            if env_value is not None:
                value = env_value
            required_consts_dict[required_var] = value
        
        return required_consts_dict
    
    def set_and_check(self, required_consts_dict: dict, generic_config, log_service):
        # Checks all variables to make sure they're not None
        for var, value in required_consts_dict.items():
            if value is None or value is '':
                    log_service.print_log_error(f"{var} variable cannot be {value} in {generic_config.moniker}_{generic_config.platform}_config")
            setattr(generic_config, var, value)
    
    ### Creating a deployment ###
    def load_deployment_config(self, generic_config, deployment_config, log_service):
        required_vars_dict: dict = self.check_and_add_vars_to_dict(generic_config)
        required_consts_dict: dict = self.load_vars_from_file(required_vars_dict, deployment_config)
        self.set_and_check(required_consts_dict, generic_config, log_service)
    
    def check_and_add_vars_to_dict(self, generic_config) -> dict:
        required_vars_dict: dict = {}
        for var, value in vars(generic_config).items():
            if not var.startswith('_') and not var == '':
                required_vars_dict[var] = value

        return  required_vars_dict
    
    def load_vars_from_file(self, required_vars_dict, deployment_config) -> dict: 
        required_consts_dict: dict = {}
        for required_var, value in required_vars_dict.items():
            env_value = deployment_config.get(required_var) 
            if env_value is not None:
                value = env_value
            required_consts_dict[required_var] = value
        
        return required_consts_dict
    

    
    # def __init__(self):

    #     ### Name your bot/sprite/service ###
    #     self.sprite_name: str = 'personal'
    #     self.document_sources_filename: str = 'personal_document_sources.yaml'
    #     self.deployment_targets: list = ['discord', 'slack']
        
    #     ### Services ###
    #     self.docker_registry: str = 'docker.io'
    #     self.docker_username: str = 'shelbyjenkins'
    #     self.docker_repo: str = 'shelby-as-a-service'
    #     self.stackpath_stack_id: str = 'shelby-stack-327b67'
    #     self.vectorstore_index: str = 'shelby-as-a-service'
    #     self.vectorstore_environment: str = 'us-central1-gcp'
    #     # The secrets for these services (API keys) must be set:
    #     # 1. Local use: in your .env file at project root
    #     # 2. Deployed: as github secrets (see .github/workflows/*.yaml for list of required secrets)
    #     
        
    #     ### Discord Sprite ###
    #     # Requests method - at least one is required
    #     self.discord_manual_requests_enabled: bool = True  # Manual allows for @discord-sprite engagement
    #     self.discord_auto_response_enabled: bool = False  # Auto responds automatically to relevant questions
    #     self.discord_auto_response_cooldown: int = 10 # Time in minutes to cooldown between auto-responding to specific users
    #     # This requires memory v2 implementation
    #     self.discord_auto_respond_in_threads: bool = False # Auto respond to messages from users in their conversations with sprite
    #     # Channel selection - at least one is required
    #     # Respond in all channels
    #     self.discord_all_channels_enabled: bool = False
    #     self.discord_all_channels_excluded_channels: Optional[List[int]] = [] # Exclude channels to reply in
    #     # Respond in specific channels
    #     self.discord_specific_channels_enabled: bool = True
    #     self.discord_specific_channel_ids: str = '1110379342745321472,1128776389227720795' # Requires at least one channel if enabled
        
    #     # Content
    #     self.discord_welcome_message = '"ima tell you about the {}."'
    #     self.discord_short_message = '"<@{}>, brevity is the soul of wit, but not of good queries. Please provide more details in your request."'
    #     self.discord_message_start = '"Running request... relax, chill, and vibe a minute."'
    #     self.discord_message_end = '"Generated by: gpt-4. Memory not enabled. Has no knowledge of past or current queries. For code see https://github.com/ShelbyJenkins/shelby-as-a-service."'
        
    #     ### Below here are optional settings that can be left on their defaults ### 
    #     # ActionAgent
    #     self.action_llm_model: str = 'gpt-4'
        
    #     # QueryAgent
    #     # pre_query_llm_model: str = 'gpt-4'
    #     self.pre_query_llm_model: str = 'gpt-3.5-turbo'
    #     self.query_llm_model: str = 'gpt-4'
    #     self.vectorstore_top_k: int = 5
    #     self.max_docs_tokens: int = 3500
    #     self.max_docs_used: int = 5
    #     self.max_response_tokens: int = 300
    #     self.openai_timeout_seconds: float = 180.0
        
    #     # APIAgent
    #     self.select_operationID_llm_model: str = 'gpt-4'
    #     self.create_function_llm_model: str = 'gpt-4'
    #     self.populate_function_llm_model: str = 'gpt-4'
        
    #     # IndexAgent
    #     self.embedding_model: Optional[str] = "text-embedding-ada-002"
    #     self.embedding_max_chunk_size: int = 8191
    #     self.embedding_batch_size: int = 100
    #     self.vectorstore_dimension: int = 1536
    #     self.vectorstore_upsert_batch_size: int = 20
    #     self.vectorstore_metric: str = "dotproduct"
    #     self.vectorstore_pod_type: str = "p1"
    #     self.preprocessor_min_length: int = 100
    #     self.text_splitter_goal_length: int = 1500
    #     self.text_splitter_max_length: int = 2000
    #     self.text_splitter_chunk_overlap: int = 100
    #     self.indexed_metadata: list[str] = ["data_source", "doc_type", "target_type", "resource_name"]
        
    #     # Don't touch these
    #     self.tiktoken_encoding_model: Optional[str] = 'text-embedding-ada-002'
    #     self.prompt_template_path: Optional[str] = os.getenv('PROMPT_TEMPLATE_PATH', 'app/prompt_templates/')
    #     self.API_spec_path: str = os.getenv('API_SPEC_PATH', 'data/minified_openAPI_specs/')

# class DeploymentConfig():
    
#     ### DeploymentConfig loads variables from YourConfig ###
#     ### Nothing should be manually set in this class ###
    
#     class DeploymentEnvs:
        
#         ### DeploymentEnvs loads variables into container environment ###
        
#         def __init__(self, your_config: YourConfig, deployment_target: str, log_agent: LogService):
            
#             self.vectorstore_index: str = your_config.vectorstore_index
#             self.vectorstore_environment: str = your_config.vectorstore_environment
            
#             match deployment_target:
#                 case 'discord':
#                     self.discord_manual_requests_enabled: bool = your_config.discord_manual_requests_enabled
#                     self.discord_auto_response_enabled: bool = your_config.discord_auto_response_enabled
#                     self.discord_auto_response_cooldown: int = your_config.discord_auto_response_cooldown
#                     self.discord_auto_respond_in_threads: bool = your_config.discord_auto_respond_in_threads
#                     # All channels
#                     self.discord_all_channels_enabled: bool = your_config.discord_all_channels_enabled
#                     if your_config.discord_all_channels_excluded_channels:
#                         self.discord_all_channels_excluded_channels: str = f'"{your_config.discord_all_channels_excluded_channels}"'
#                     # Specific channels
#                     self.discord_specific_channels_enabled: bool = your_config.discord_specific_channels_enabled
#                     if self.discord_specific_channels_enabled:
#                         self.discord_specific_channel_ids: str = f'"{your_config.discord_specific_channel_ids}"'
#                     # "" are required for formating in github actions workflow, but they need to be removed for use by discord sprite
#                     self.discord_welcome_message: str = your_config.discord_welcome_message
#                     self.discord_short_message: str = your_config.discord_short_message
#                     self.discord_message_start: str = your_config.discord_message_start
#                     self.discord_message_end: str = your_config.discord_message_end
#                 case 'slack':
#                     pass
            
#             # Loads from document sources config file
#             self.document_sources_filepath = os.path.join('index', your_config.document_sources_filename)
#             with open(self.document_sources_filepath, 'r') as stream:
#                 data_sources = yaml.safe_load(stream)
                
#             namespaces_from_file = {key: value['description'] for key, value in data_sources.items()}
#             # self.vectorstore_namespaces = f'"{namespaces_from_file}"'
#             self.vectorstore_namespaces = f"'{json.dumps(namespaces_from_file)}'"
            
#             your_config.config_check(self, deployment_target, log_agent)
            
#     def __init__(self, your_config: YourConfig, deployment_target: str, log_agent: LogService):
    
#         self.your_config = your_config
#         self.deployment_target = deployment_target
#         self.deployment_envs = self.DeploymentEnvs(your_config, deployment_target, log_agent)
        
#         ### AppConfig loads variables from the env or falls to defaults set in DeploymentConfig ###
#         self.sprite_name: str = self.your_config.sprite_name
        
#         ### services ###
#         self.docker_registry: str = self.your_config.docker_registry
#         self.docker_username: str = self.your_config.docker_username
#         self.docker_repo: str = self.your_config.docker_repo
#         self.stackpath_stack_id: str = self.your_config.stackpath_stack_id
        
#         self.docker_server: str = f'docker.io/{self.docker_username}/{self.docker_repo}'
#         self.docker_image_path: str = f'{self.docker_username}/{self.docker_repo}:{deployment_target}-latest'
#         self.github_action_workflow_name: str = f'{self.sprite_name.lower()}_{deployment_target.lower()}_build_deploy'
#         self.workload_name: str = f'shelby-as-a-service-{self.sprite_name.lower()}-{deployment_target.lower()}-sprite'
#         self.workload_slug: str = f'{self.sprite_name.lower()}-{self.deployment_target.lower()}-sprite'
            
#         self.your_config.config_check(self, self.deployment_target, log_agent)
     
# class AppConfig():
    
#     ### Nothing should be manually set in this class ###
#     ### AppConfig loads variables from the env or fails to defaults set in YourConfig ###
    
#     def __init__(self, deployment_target: str, log_agent: LogService):
        
#         self.your_config = YourConfig()
#         self.deployment_target: str = os.getenv('DEPLOYMENT_TARGET', deployment_target)         
#         ### secrets ###
#         # For local development set private vars in .env
#         # For deployment use github secrets which will be loaded into the container at deployment
#         self.openai_api_key: str = os.getenv('OPENAI_API_KEY') 
#         self.pinecone_api_key: str = os.getenv('PINECONE_API_KEY') 

#         ### config ###
#         self.vectorstore_index: str = os.getenv('VECTORSTORE_INDEX', self.your_config.vectorstore_index)
#         self.vectorstore_environment: str = os.getenv('VECTORSTORE_ENVIRONMENT', self.your_config.vectorstore_environment)
        
#         match self.deployment_target:
#             case 'discord':
#                 self.discord_token: str = os.getenv('DISCORD_TOKEN') 
#                 self.discord_manual_requests_enabled: bool = os.getenv('DISCORD_MANUAL_REQUESTS_ENABLED', self.your_config.discord_manual_requests_enabled)
#                 self.discord_auto_response_enabled: bool = os.getenv('DISCORD_AUTO_RESPONSE_ENABLED', self.your_config.discord_manual_requests_enabled)
#                 self.discord_auto_response_cooldown: int = os.getenv('DISCORD_AUTO_RESPONSE_COOLDOWN', self.your_config.discord_auto_response_cooldown)
#                 self.discord_auto_respond_in_threads: bool = os.getenv('DISCORD_AUTO_RESPOND_IN_THREADS', self.your_config.discord_auto_respond_in_threads)
                
#                 # All channels
#                 self.discord_all_channels_enabled: bool = os.getenv('DISCORD_ALL_CHANNELS_ENABLED', self.your_config.discord_all_channels_enabled)
#                 if self.discord_all_channels_enabled:
#                     self.discord_all_channels_excluded_channels: Optional[List[int]] = [int(id) for id in os.getenv('DISCORD_ALL_CHANNELS_EXCLUDED_CHANNELS', '').split(',') if id]
#                     if not self.discord_all_channels_excluded_channels:
#                         self.discord_all_channels_excluded_channels: Optional[List[int]] = self.your_config.discord_all_channels_excluded_channels

#                 # Specific channels
#                 self.discord_specific_channels_enabled: bool = os.getenv('DISCORD_SPECIFIC_CHANNELS_ENABLED', self.your_config.discord_specific_channels_enabled)
#                 if self.discord_specific_channels_enabled:
#                     self.discord_specific_channel_ids: Optional[List[int]] = [int(id) for id in os.getenv('DISCORD_SPECIFIC_CHANNEL_IDS', '').split(',') if id]
#                     if not self.discord_specific_channel_ids:
#                         self.discord_specific_channel_ids: Optional[List[int]] = self.your_config.discord_specific_channel_ids
                        
#                 # "" are required for formating in github actions workflow, but they need to be removed for use by discord sprite
#                 self.discord_welcome_message: str = os.getenv('DISCORD_WELCOME_MESSAGE', self.your_config.discord_welcome_message).strip('"')
#                 self.discord_short_message: str = os.getenv('DISCORD_SHORT_MESSAGE', self.your_config.discord_short_message).strip('"')
#                 self.discord_message_start: str = os.getenv('DISCORD_MESSAGE_START', self.your_config.discord_message_start).strip('"')
#                 self.discord_message_end: str = os.getenv('DISCORD_MESSAGE_END', self.your_config.discord_message_end).strip('"')
            
#             case 'slack':
#                 self.slack_bot_token: str = os.getenv('SLACK_BOT_TOKEN') 
#                 self.slack_app_token: str = os.getenv('SLACK_APP_TOKEN')
        
#         # ActionAgent
#         self.action_llm_model: str = os.getenv('ACTION_LLM_MODEL', self.your_config.action_llm_model)
        
#         # QueryAgent
#         self.pre_query_llm_model: str = os.getenv('PRE_QUERY_LLM_MODEL', self.your_config.pre_query_llm_model)
#         self.query_llm_model: str = os.getenv('QUERY_LLM_MODEL', self.your_config.query_llm_model)
#         self.vectorstore_top_k: int = int(os.getenv('VECTORSTORE_TOP_K', self.your_config.vectorstore_top_k))
#         self.max_docs_tokens: int = int(os.getenv('MAX_DOCS_TOKENS', self.your_config.max_docs_tokens))
#         self.max_docs_used: int = int(os.getenv('MAX_DOCS_USED', self.your_config.max_docs_used))
#         self.max_response_tokens: int = int(os.getenv('MAX_RESPONSE_TOKENS', self.your_config.max_response_tokens))
#         self.openai_timeout_seconds: float = float(os.getenv('OPENAI_TIMEOUT_SECONDS', self.your_config.openai_timeout_seconds))
        
#         # APIAgent
#         self.select_operationID_llm_model: str = os.getenv('SELECT_OPERATIONID_LLM_MODEL', self.your_config.select_operationID_llm_model)
#         self.create_function_llm_model: str = os.getenv('CREATE_FUNCTION_LLM_MODEL', self.your_config.create_function_llm_model)
#         self.populate_function_llm_model: str = os.getenv('POPULATE_FUNCTION_LLM_MODEL', self.your_config.populate_function_llm_model)
        
#         # IndexAgent
#         self.embedding_model: str = self.your_config.embedding_model
#         self.embedding_max_chunk_size: int = self.your_config.embedding_max_chunk_size
#         self.embedding_batch_size: int = self.your_config.embedding_batch_size
#         self.vectorstore_dimension: int = self.your_config.vectorstore_dimension
#         self.vectorstore_upsert_batch_size: int = self.your_config.vectorstore_upsert_batch_size
#         self.vectorstore_metric: str = self.your_config.vectorstore_metric
#         self.vectorstore_pod_type: str = self.your_config.vectorstore_pod_type
#         self.preprocessor_min_length: int = self.your_config.preprocessor_min_length
#         self.text_splitter_goal_length: int = self.your_config.text_splitter_goal_length
#         self.text_splitter_max_length: int = self.your_config.text_splitter_max_length
#         self.text_splitter_chunk_overlap: int = self.your_config.text_splitter_chunk_overlap
#         self.indexed_metadata: list[str] = self.your_config.indexed_metadata
        
#         # Don't touch these
#         self.tiktoken_encoding_model: str = self.your_config.tiktoken_encoding_model
#         self.prompt_template_path: str = self.your_config.prompt_template_path
#         self.API_spec_path: str = self.your_config.API_spec_path

#         # Loads from document sources config file or env
#         self.document_sources_filename = os.getenv('DOCUMENT_SOURCES_FILENAME', self.your_config.document_sources_filename)
#         self.document_sources_filepath = os.path.join('index', self.your_config.document_sources_filename)
#         with open(self.document_sources_filepath, 'r') as stream:
#             data_sources = yaml.safe_load(stream)
            
#         self.namespaces_from_file = {key: value['description'] for key, value in data_sources.items()}
        
#         if os.getenv('VECTORSTORE_NAMESPACES') is not None:
#             self.vectorstore_namespaces = json.loads(os.getenv('VECTORSTORE_NAMESPACES'))
#         else:
#             self.vectorstore_namespaces = self.namespaces_from_file
        
#         self.your_config.config_check(self, deployment_target, log_agent)
        