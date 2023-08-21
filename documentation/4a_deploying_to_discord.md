1.  First, we'll create your bot in the Discord dev portal: `https://discord.com/developers/applications`
    1. `General Information` tab just requires the app name and image
    2. `OAuth2 -> General` tab requires no action.
    3. `Bot` tab requires
       1. The bot name and avatar image
       2. Every toggle can be turned off and every check can be left blank here!
       3. Get the bot token here to be saved in your `.env` as `DISCORD_TOKEN`
    4. Add your bot to the server by the `OAuth2 -> URL Generator` tab.
       1. Click nothing but the bot checkbox, scroll to the bottom of the page, copy the url, and paste it into your browser.
   
2. Now we'll update the `DiscordConfig` class in your `app/deployments/<your_deployment_name>/deployment_config.py`
   1. In your discord server get the `channel_id` of the text channel you want the bot to response in and add it to the list of `discord_enabled_servers`
   2. If you want to lock it so it only listens/responds within a specific channel add that here: `discord_specific_channel_ids`
   3. Every other settings is optional and populated at run time from the defaults.

3. Run `python app/run_local_test.py --make_deployment <your_deployment_name>` again.
   1. It will generate a github actions workflow file like `.github/workflows/<your_deployment_name>_deployment.yaml` (it will also generate a dockerfile and requirements.txt file in your deployments folder.)
   2. There will be a list of secrets you need to add to your github actions workflow like:

        `<your_deployment_name>_STACKPATH_API_CLIENT_SECRET:  ${{ secrets.<your_deployment_name>_STACKPATH_API_CLIENT_SECRET }}`

4. For each of these add them to your forked github repo by going to `settings -> Secrets and variables -> Actions`
   1. Add each. The names will be the portion after `secrets.` so `STACKPATH_CLIENT_ID`, `<your_deployment_name>_API_CLIENT_SECRET`, etc
5. Go to the `Actions` tab in your repo, find your newly created workflow, likely `<your_deployment_name>_deployment`, and click `Run workflow`
   1. If everything works your bot should ping your discord channel in a few minutes when it comes online.

# Troubleshooting

I suggest checking logs in two places:
1. If you click into the github actions deploy workflow you'll find an entry `Run deployment script` which may be useful
2. In the stackpath portal look at `workload -> instance -> logs`

Generally it's just a config issue which can easily be fixed, but if not create an issue with the information from these logs, and I can help!