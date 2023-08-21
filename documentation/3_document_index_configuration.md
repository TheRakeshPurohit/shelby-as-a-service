1. First we will setup our document index in this file `app/deployments/<your_deployment_name>/index_description.yaml`
   1. You don't need an existing index in Pinecone. Index_service will automatically create one for you in the name you provide in the config.
   2. I suggest using a `gitbook` or a `sitemap` if possible because they have a better compatibility than the `generic` website function.
   3. Currently available document sources are available in `app/services/index_service.py` in the `DataSourceConfig` class. In theory, implementing other sources should be easy and Langchain has many available!
2. Once `index_description.yaml` is configured and a data source is enabled we'll initiate the index_service.
   1. Run `python app/run_local_test.py --index_management <your_deployment_name>` (or just comment out the relevant code and run through the debugger)
   2. This will go through your data sources one at a time. It will scrape them, process them, create embeddings, and finally upsert the embeddings to pinecone. It can take some time depending on the size of your document sources.
   3. Check the logs in `app/deployments/<your_deployment_name>/logs/<your_deployment_name>_index_agent.md` to confirm your data has been uploaded to pinecone.
   4. The document chunks that are uploaded are saved in `app/deployments/<your_deployment_name>/index/outputs/<data_domain>` for your viewing pleasure. Also, the index_service uses those document chunks on future runs - in the case the freshly scrapped document chunks match the existing chunks, further processing is skipped.
3. Right now we don't have index_service set up for anything besides ingesting docs. However, the code is written to delete, clear the index as well as clearing namespaces (the deployment name). Just comment out the required lines in `run_local_test.py` if you need those functions.

Next -> [4a. Deploying to Discord ](https://github.com/ShelbyJenkins/shelby-as-a-service/blob/main/documentation/4a_deploying_to_discord.md)