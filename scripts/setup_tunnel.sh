#!/bin/bash
# Setup script for WebSocket-compatible tunneling solutions

echo "=================================="
echo "AI Concierge - Tunnel Setup"
echo "=================================="
echo ""
echo "ngrok free tier blocks WebSocket connections (403 Forbidden)."
echo "You need a WebSocket-compatible tunnel for Twilio Media Streams."
echo ""
echo "Choose a solution:"
echo ""
echo "1. Cloudflare Tunnel (RECOMMENDED - Free, Fast, WebSocket support)"
echo "2. localhost.run (Quick, Free, WebSocket support)"
echo "3. ngrok with authentication (May work, depends on account)"
echo ""

read -p "Enter choice (1-3): " choice

case $choice in
  1)
    echo ""
    echo "Installing Cloudflare Tunnel..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
      # macOS
      if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew not found. Install from: https://brew.sh"
        exit 1
      fi
      brew install cloudflare/cloudflare/cloudflared
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
      # Linux
      wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
      sudo dpkg -i cloudflared-linux-amd64.deb
      rm cloudflared-linux-amd64.deb
    else
      echo "Please install cloudflared manually from:"
      echo "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
      exit 1
    fi
    
    echo ""
    echo "✅ Cloudflare Tunnel installed!"
    echo ""
    echo "To start the tunnel, run:"
    echo "  cloudflared tunnel --url http://localhost:8080"
    echo ""
    echo "Then copy the URL (e.g., https://random-words.trycloudflare.com)"
    echo "and set it as PUBLIC_DOMAIN in your .env file (without https://):"
    echo "  PUBLIC_DOMAIN=random-words.trycloudflare.com"
    ;;
    
  2)
    echo ""
    echo "Using localhost.run..."
    echo ""
    echo "To start the tunnel, run:"
    echo "  ssh -R 80:localhost:8080 localhost.run"
    echo ""
    echo "Then copy the URL from the output"
    echo "and set it as PUBLIC_DOMAIN in your .env file (without https://):"
    echo "  PUBLIC_DOMAIN=your-subdomain.localhost.run"
    ;;
    
  3)
    echo ""
    echo "Setting up ngrok authentication..."
    echo ""
    read -p "Enter your ngrok authtoken (from https://dashboard.ngrok.com/get-started/your-authtoken): " token
    
    if [ -z "$token" ]; then
      echo "❌ No token provided"
      exit 1
    fi
    
    ngrok config add-authtoken "$token"
    echo ""
    echo "✅ ngrok authenticated!"
    echo ""
    echo "To start ngrok, run:"
    echo "  ngrok http 8080"
    echo ""
    echo "Then copy the URL and set it as PUBLIC_DOMAIN in your .env file"
    ;;
    
  *)
    echo "Invalid choice"
    exit 1
    ;;
esac

echo ""
echo "=================================="
echo "Next Steps:"
echo "=================================="
echo "1. Start your tunnel using the command above"
echo "2. Update PUBLIC_DOMAIN in .env with your tunnel URL"
echo "3. Restart your server: python -m concierge.server"
echo "4. Test your reservation system"

