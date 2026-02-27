#!/bin/bash
# Quick setup script for MikroBot

set -e

echo "════════════════════════════════════════════════════════════════"
echo "  MikroBot Extended — Quick Setup"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "✓ Found existing .env file"
    source .env
else
    echo "Creating .env from template..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and set your BOT_TOKEN"
    echo "   Get token from: https://t.me/BotFather"
    echo ""
    read -p "Enter your bot token now (or press Enter to edit .env manually): " token
    if [ ! -z "$token" ]; then
        sed -i "s/BOT_TOKEN=.*/BOT_TOKEN=$token/" .env
        echo "✓ Token saved to .env"
    fi
fi

# Check Python version
echo ""
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo "✓ Python $python_version detected"

# Install dependencies
echo ""
echo "Installing dependencies..."
if python3 -m pip --version &>/dev/null; then
    # Try without --break-system-packages first
    if python3 -m pip install -r requirements.txt &>/dev/null; then
        echo "✓ Dependencies installed"
    else
        # Fallback to --break-system-packages for Python 3.11+
        python3 -m pip install -r requirements.txt --break-system-packages
        echo "✓ Dependencies installed (system packages)"
    fi
else
    echo "❌ pip not found. Please install python3-pip:"
    echo "   Ubuntu/Debian: sudo apt install python3-pip"
    echo "   CentOS/RHEL:   sudo yum install python3-pip"
    exit 1
fi

# Create data directory
mkdir -p data
echo "✓ Created data directory"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Setup Complete!"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check if token is set
source .env 2>/dev/null || true
if [ "$BOT_TOKEN" = "PUT_TOKEN_HERE" ] || [ -z "$BOT_TOKEN" ]; then
    echo "⚠️  WARNING: BOT_TOKEN not configured!"
    echo ""
    echo "Next steps:"
    echo "  1. Edit .env and set your BOT_TOKEN"
    echo "  2. Get token from: https://t.me/BotFather"
    echo "  3. Run: python3 bot.py"
else
    echo "✓ Bot token configured"
    echo ""
    echo "Ready to start!"
    echo ""
    read -p "Start the bot now? (y/n): " start_now
    if [ "$start_now" = "y" ] || [ "$start_now" = "Y" ]; then
        echo ""
        echo "Starting MikroBot..."
        echo "Press Ctrl+C to stop"
        echo ""
        python3 bot.py
    else
        echo ""
        echo "To start manually, run:"
        echo "  python3 bot.py"
    fi
fi

echo ""
echo "For detailed setup instructions, see SETUP.md"
echo "════════════════════════════════════════════════════════════════"
