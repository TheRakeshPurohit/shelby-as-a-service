1. Create a `deployment` using the command:
   1.  `python app/run_local_test.py --make_deployment <your_deployment_name>`
   2. This will duplicate the template and create a folder `app/deployments/<your_deployment_name>` with the required config files.
2. Create accounts for all the required services.
   1. Store the secrets for those services in `app/deployments/<your_deployment_name>/.env`
   2. This is only used for locally testing and not required, but can be a convenient place to store your secrets.
3. Your other configuration files are the:
   1. `app/deployments/<your_deployment_name>/deployment_config.py` which is mostly optional settings that configures the behavior of the bots and agents functionality.
      1. Add your Docker information here before deploying.
   2. `app/deployments/<your_deployment_name>/index_description.yaml` configures your vectorstore index. It's only used when managing your index such as ingesting new documents.
4. Finally, once we're finished setting these all up in the next steps, we'll use `python app/run_local_test.py --make_deployment <your_deployment_name>` once again to build the files for deployment like the github actions workflow file and the dockerfile.

Next -> [3. Document index configuration](https://github.com/ShelbyJenkins/shelby-as-a-service/blob/main/documentation/3_document_index_configuration.md)

