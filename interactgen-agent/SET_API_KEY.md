# How to Set Groq API Key

## Option 1: Set in Current PowerShell Session (Quick)

Run this command in PowerShell before starting the chatbot:

```powershell
$env:GROQ_API_KEY="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"
```

Then start the chatbot in the same window:
```powershell
python chatbot/app.py
```

## Option 2: Set Permanently (Recommended)

### For Current User (Persistent):
```powershell
[System.Environment]::SetEnvironmentVariable('GROQ_API_KEY', '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', 'User')
```

**Note**: After this, close and reopen PowerShell, then the key will be available in all new sessions.

## Option 3: Use python-dotenv (For Development)

The chatbot already supports loading from `.env` file. Just create one:

**In PowerShell:**
```powershell
@"
GROQ_API_KEY=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
"@ | Out-File -FilePath .env -Encoding UTF8
```

## Verify It's Set

```powershell
echo $env:GROQ_API_KEY
```

Should output: `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`

## Then Start Chatbot

```powershell
python chatbot/app.py
```

Open browser to: http://localhost:5000

---

**Good News**: Your chatbot is already working! I saw in the logs it successfully scraped Google (79 elements) and Flipkart (979 elements). The API key is just needed for the LLM planner step to generate automation instructions.
