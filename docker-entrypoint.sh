#!/bin/bash
set -e

# Create data directory if it doesn't exist
mkdir -p /app/src/data

# Check if setup has been completed
if [ ! -f "/app/src/data/setup_complete.json" ]; then
    echo "Initial setup required. The setup wizard will be available at http://localhost:5000/api/setup/setup"
    echo "Please complete the setup to configure your Plex Portal."
else
    echo "Setup already completed. Loading configuration from file."
fi

# Start the application
exec python -m src.main
