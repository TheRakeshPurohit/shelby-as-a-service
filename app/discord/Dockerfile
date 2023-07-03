# Use an official Python runtime as a parent image
FROM python:3-slim-buster

# Set the working directory in the container to /app
WORKDIR /bots

# Copy all files and folders from the bots directory
COPY ./ ./ 

# Install python packages
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app/discord_bot.py"]



