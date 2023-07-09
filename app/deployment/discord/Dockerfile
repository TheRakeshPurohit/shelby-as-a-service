# Use an official Python runtime as a parent image
FROM python:3-slim-buster

# Set the working directory in the container to /shelby-as-a-service
WORKDIR /shelby-as-a-service

# Copy all files and folders from the root directory
COPY ./ ./ 

# Install python packages
RUN pip install --no-cache-dir -r app/deployment/discord/discord_requirements.txt

CMD ["python", "app/discord_sprite.py"]
