# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install the project and its dependencies
RUN pip install --no-cache-dir .

# Create a volume for the workspace data
VOLUME /data

# Set environment variables for non-interactive use
ENV PYTHONUNBUFFERED=1

# Run the bot by default, using /data as the workspace
ENTRYPOINT ["b0"]
CMD ["--workspace", "/data"]
