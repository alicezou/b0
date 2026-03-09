#!/bin/bash

# start_clean.sh - Clean up and start the program

# Ensure we are in the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Run cleanup
if [ -f "./cleanup.sh" ]; then
    ./cleanup.sh
else
    echo "cleanup.sh not found, skipping cleanup."
fi

echo "Starting the program..."

# Check if .env exists, if not warn the user
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. You might need to set up your API keys."
fi

# Run the program
python3 -m b0
