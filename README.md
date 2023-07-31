<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a name="readme-top"></a>
<!--
*** Thanks for checking out the Best-README-Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Don't forget to give the project a star!
*** Thanks again! Now go create something AMAZING! :D
-->



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]



<!-- PROJECT LOGO
<br />
<div align="center">
  <a href="https://github.com/ShelbyJenkins/shelby-as-a-service">
    <img src="images/logo.png" alt="Logo" width="80" height="80">
  </a>

<h3 align="center">project_title</h3>

  <p align="center">
    project_description
    <br />
    <a href="https://github.com/ShelbyJenkins/shelby-as-a-service"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/ShelbyJenkins/shelby-as-a-service">View Demo</a>
    ·
    <a href="https://github.com/ShelbyJenkins/shelby-as-a-service/issues">Report Bug</a>
    ·
    <a href="https://github.com/ShelbyJenkins/shelby-as-a-service/issues">Request Feature</a>
  </p>
</div> -->



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->

## Production-ready LLM Agents. Just add API keys

[![Discord Screen Shot][discord-screenshot]](documentation/discord-example.png)
[![Slack Screen Shot][slack-screenshot]](documentation/slack-example.png)

### Features

The gulf between 'hello world' and something useful is what shelby-as-a-service (SaaS) solves. 

* Easy:
  * Configuration requires only API keys.
  * Step-by-step guides.
  * Automatically builds dockerfile and github actions workflow to deploy to container.
* Context enriched queries, retrieval augmented generation (RAG), prompt stuffing, questions on docs, etc
  * Automatically scrapes, processes, and uploads data from websites, gitbooks, sitemaps, and OpenAPI specs.
  * Superior Document retrieval.
    * Performs semantic search with sparse/dense embeddings by default.
    * Generates additional search keywords for better semantic search results.
    * Checks if documents are relevant by asking GPT, "Which of these documents are relevant?"
    * Superior document pre-processing with BalancedRecursiveCharacterTextSplitter and thoughtful parsing.
* Pre-configured Slack and Discord bots (lets call them 'Sprites' for this project).
* Tweaking not required, but all the knobs are at your disposal in the configuration folder.
  * All configuration variables are stored and loaded through  shelby_agent_config.py
  * All data sources are added through template_document_sources.yaml
  * All prompts are easily accessbile through prompt_template folder

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ROADMAP -->
## Roadmap

* Enable memory for conversational queries
* Enable the bot to make request to *any* API with an OpenAPI spec
* Improve and add additional document sources
* Speech to text job interview agent
* Add service providers
* Installable via PIP

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

# Out of date!
I made some huge changes this weekend, and ran out of time to update the documentation. In theory, everything works. Except maybe not. By the end of the week I should have the documentation updated to reflect the changes.

This will be covered in three steps:

1. Installation -> https://github.com/ShelbyJenkins/shelby-as-a-service/blob/main/documentation/INSTALLATION.md
2. Configuration -> https://github.com/ShelbyJenkins/shelby-as-a-service/blob/main/documentation/CONFIGURATION.md
3. Deploying for
   1. Discord -> https://github.com/ShelbyJenkins/shelby-as-a-service/blob/main/documentation/DEPLOYING_FOR_DISCORD.md
   2. Slack -> https://github.com/ShelbyJenkins/shelby-as-a-service/blob/main/documentation/DEPLOYING_FOR_SLACK.md

### Prerequisites

You will need and API key for the following services:

Free:
* Discord -> https://discord.com/developers/docs/intro
* or Slack -> https://api.slack.com/apps
* Pinecone -> https://www.pinecone.io/
* Github -> https://github.com/
* Docker -> https://www.docker.com/

Paid:
* OpenAI API (GPT-3.5 is tenable) -> https://platform.openai.com/overview
* Stackpath (I will add other compute providers if requested.) -> https://www.stackpath.com/


<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

I would love any help adding features!

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Shelby Jenkins - Here or Linkedin https://www.linkedin.com/in/jshelbyj/

Project Link: [https://github.com/ShelbyJenkins/shelby-as-a-service](https://github.com/ShelbyJenkins/shelby-as-a-service)

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/shelbyjenkins/shelby-as-a-service.svg?style=for-the-badge
[contributors-url]: https://github.com/ShelbyJenkins/shelby-as-a-service/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/ShelbyJenkins/shelby-as-a-service.svg?style=for-the-badge
[forks-url]: https://github.com/ShelbyJenkins/shelby-as-a-service/network/members
[stars-shield]: https://img.shields.io/github/stars/ShelbyJenkins/shelby-as-a-service.svg?style=for-the-badge
[stars-url]: https://github.com/ShelbyJenkins/shelby-as-a-service/stargazers
[issues-shield]: https://img.shields.io/github/issues/ShelbyJenkins/shelby-as-a-service.svg?style=for-the-badge
[issues-url]: https://github.com/ShelbyJenkins/shelby-as-a-service/issues
[license-shield]: https://img.shields.io/github/license/ShelbyJenkins/shelby-as-a-service.svg?style=for-the-badge
[license-url]: https://github.com/ShelbyJenkins/shelby-as-a-service/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://www.linkedin.com/in/jshelbyj/

[discord-screenshot]: documentation/discord-example.png
[slack-screenshot]: documentation/slack-example.png

[python]: https://img.shields.io/badge/python-000000?style=for-the-badge&logo=python&logoColor=white
[python-url]: https://www.python.org/
[langchain]: https://img.shields.io/badge/langchain-20232A?style=for-the-badge&logo=langchain&logoColor=61DAFB
[langchain-url]: https://python.langchain.com/
[haystack]: https://img.shields.io/badge/haystack-35495E?style=for-the-badge&logo=haystack&logoColor=4FC08D
[haystack-url]: https://github.com/deepset-ai/haystack
[discord.py]: https://img.shields.io/badge/discord.py-DD0031?style=for-the-badge&logo=discord.py&logoColor=white
[discord.py-url]: https://github.com/Rapptz/discord.py
[slack-bolt]: https://img.shields.io/badge/slack-bolt-4A4A55?style=for-the-badge&logo=slack-bolt&logoColor=FF3E00
[slack-bolt-url]: https://github.com/slackapi/bolt-python


* [![python][python]][python-url]
* [![langchain][langchain]][langchain-url]
* [![haystack][haystack]][haystack-url]
* [![discord.py][discord.py]][discord.py-url]
* [![slack-bolt][slack-bolt]][slack-bolt-url]