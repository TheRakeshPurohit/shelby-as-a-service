1. Create a accounts for all the required services
2. Add the public information to `app/configuration/shelby_agent_config.py`
3. Create a `.env` file in your project root and add the private information like: 

```
OPENAI_API_KEY=n
PINECONE_API_KEY=n
PINECONE_ENV=n
DOCKER_USERNAME=n
DOCKER_TOKEN=n
STACKPATH_CLIENT_ID=n
STACKPATH_API_CLIENT_SECRET=n
# I'll give more instruction about this in the discord/slack guides
DISCORD_TOKEN=n
DISCORD_CHANNEL_IDS=n,n
SLACK_BOT_TOKEN=n
SLACK_APP_TOKEN=n
```
4. Make a copy of `app/configuration/template_document_sources.yaml`
   1. Rename it something like `personal_document_sources.yaml`
   2. Add that file to shelby_agent_config.py `document_sources_filename` variable.
   3. Populate it with the data sources you want to index
5. Open up `app/local_stand_alone_actions.py`
   1. Make sure `manage_index()` **is not** commented out and then run the script.
   2. This should scrape your data source and upsert the embeddings to pinecone.
   3. Check the logs in `logs/IndexAgent.log` to confirm your data has been uploaded to pinecone.
   4. The chunks that are uploaded are saved in `outputs/document_chunks` for your viewing pleasure.
6. At this point, you can run the ShelbyAgent QA function locally with `local_stand_alone_actions.py`
   1. Make sure `manage_index()` **is** commented out,
   2. And `asyncio.run(run_shelby_agent(request))` **is not** commented out and then run the script.