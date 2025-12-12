# Quick Start Guide

## Prerequisites

- Python 3.8 or higher
- Groq API Key (free at https://console.groq.com)

## Installation (Windows)

```powershell
# Navigate to project
cd d:\Project\Hackathon\InteractGenxSRM-44\interactgen-agent

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Configure API Key

```powershell
# Set environment variable
$env:GROQ_API_KEY="gsk_your_api_key_here"
```

## Run Chatbot

```powershell
# Start server
python chatbot/app.py
```

Open browser to: **http://localhost:5000**

## Try It!

1. Enter URL: `https://www.google.com`
2. Enter query: "Search for 'AI news' and click first result"
3. Click Execute
4. Watch automation run in real-time!

## CLI Alternative

```powershell
# Run complete workflow
python src/orchestrator/orchestrator.py --query "Find contact page" --url "https://example.com"
```

## Troubleshooting

**No Groq API Key**: Get free key at https://console.groq.com  
**Playwright error**: Run `playwright install chromium`
**Port 5000 in use**: Change port in `.env`: `CHATBOT_PORT=5001`

## Example Queries

- "Search for 'machine learning' on Google"
- "Find laptops under $1000 on Amazon"
- "Search for 'Python' on GitHub"
- "Fill contact form with name John and email john@example.com"
