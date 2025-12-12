#!/bin/bash
# Start InteractGen Chatbot

echo "🚀 Starting InteractGen Chatbot..."
echo ""

# Check for Groq API key
if [ -z "$GROQ_API_KEY" ]; then
    echo "❌ ERROR: GROQ_API_KEY environment variable not set"
    echo "Get your free API key at: https://console.groq.com"
    echo ""
    echo "Then set it with:"
    echo "  export GROQ_API_KEY='your_key_here'"
    exit 1
fi

echo "✓ GROQ_API_KEY found"

# Check if Playwright browsers are installed
if ! python -c "from playwright.sync_api import sync_playwright; sync_playwright().start()" 2>/dev/null; then
    echo "Installing Playwright browsers..."
    playwright install chromium
fi

echo "✓ Playwright ready"
echo ""

# Start the chatbot server
echo "Starting chatbot server on http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

cd "$(dirname "$0")/.." || exit
python chatbot/app.py
