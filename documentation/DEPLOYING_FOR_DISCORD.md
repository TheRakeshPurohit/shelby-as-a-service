1. Create you bot here `https://discord.com/developers/applications`
2. `General Information` tab just requires the app name and image
3. `OAuth2 -> General` tab requires no action.
4. `Bot` tab requires
   1. The bot name and avatar image
   2. Every toggle can be turned off and every check can be left blank here!
   3. Get the bot token here to be saved in your `.env` as `DISCORD_TOKEN`
5. Add your bot to the server by the `OAuth2 -> URL Generator` tab.
   1. Click nothing but the bot checkbox, scroll to the bottom of the page, copy the url, and paste it into your browser.
6. In your discord server get the `channel_id` of the text channel you want the bot to response in.
7. Run `app/generate_deployment_scripts.py`
   1. It will generate something like `.github/workflows/personal_discord_build_deploy.yaml`
   2. There will be a list of secrets you need to add to your github actions workflow like:


            ### Services Secrets to be added to github secrets ###
            STACKPATH_CLIENT_ID: ${{ secrets.STACKPATH_CLIENT_ID }}
            STACKPATH_API_CLIENT_SECRET: ${{ secrets.STACKPATH_API_CLIENT_SECRET }}
            OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
            PINECONE_API_KEY: ${{ secrets.PINECONE_API_KEY }}
            DOCKER_TOKEN: ${{ secrets.DOCKER_TOKEN }}  

            DISCORD_TOKEN: ${{ secrets.PERSONAL_SPRITE_DISCORD_TOKEN }}
            DISCORD_CHANNEL_IDS: ${{ secrets.PERSONAL_SPRITE_DISCORD_CHANNEL_IDS }}

7. For each of these add them to your forked github repo by going to `settings -> Secrets and variables -> Actions`
   1. Add each. The names will be the portion after `secrets.` so `STACKPATH_CLIENT_ID`, `STACKPATH_API_CLIENT_SECRET`, etc
8. Go to the `Actions` tab in your repo, find your newly created workflow, likely `personal_discord_build_deploy`, and click `Run workflow`
   1. If everything works your bot should ping your discord channel in a few minutes when it comes online.

# Troubleshooting

I suggest checking logs in two places:
1. If you click into the github actions deploy workflow you'll find an entry `Run deployment script` which may be useful
2. In the stackpath portal look at `workload -> instance -> logs`

Generally it's just a config issue which can easily be fixed, but if not create an issue with the information from these logs, and I can help!