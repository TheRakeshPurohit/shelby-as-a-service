1. Fork the repo
2. Create codespace from your forked repo
   1. In the main repo click code, and then codespaces.
   2. Open codespace in vscode.
3. Install git 
   1. `apt-get update`
   2. `apt-get install -y git`
4. Install python dependencies
   1. `pip install requirements.txt`
5. Lang chain and LLM-OpenAPI-minifier should install but if not install them
   1. `pip install git+https://github.com/ShelbyJenkins/langchain`
   2. `pip install git+https://github.com/ShelbyJenkins/LLM-OpenAPI-minifier`
   3. Soon I will integrate these into the main package.
6. Done