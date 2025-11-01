#!/bin/bash
# Start the AI Concierge Voice Server

set -e

echo "Starting AI Concierge Voice Server..."
echo "=================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Check if PUBLIC_DOMAIN is set
if ! grep -q "^PUBLIC_DOMAIN=..*" .env; then
    echo "Warning: PUBLIC_DOMAIN not configured in .env"
    echo "You'll need to set this for Twilio webhooks to work"
    echo ""
fi

# Start the server
echo "Starting server on port 8080..."
echo "Press Ctrl+C to stop"
echo ""

python -m concierge.server

