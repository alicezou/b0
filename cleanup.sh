#!/bin/bash

# cleanup.sh - Clean up all generated files to allow a fresh start

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting cleanup of generated files...${NC}"

# Remove Python cache and build artifacts
echo -e "Cleaning Python artifacts..."
find . -type d -name "__pycache__" -exec rm -rf {} +
rm -rf .pytest_cache
rm -rf build/
rm -rf dist/
rm -rf *.egg-info/

# Remove user data and state files
echo -e "Cleaning user data and state files..."
rm -f USER-*.md
rm -f INTAKE-*.json
rm -f reminders.json
rm -f authorized_users
rm -f tokens
rm -f RUNTIME-MEMORY.md

# Optional: Clean tmp directory if it exists
if [ -d "tmp" ]; then
    echo -e "Cleaning tmp directory..."
    rm -rf tmp/*
fi

echo -e "${GREEN}Cleanup complete. The program can now be started cleanly.${NC}"
