# InteractGen - AI-Powered Web Automation

🤖 **InteractGen** is a multi-agent web automation system that converts natural language queries into executable browser automation steps. Built with LangGraph architecture, Groq LLM, and vision-enhanced element selection.

## 🌟 Features

- **Natural Language Interface**: Describe what you want to automate in plain English
- **Universal Website Support**: Works on any website via URL input  
- **Vision-Enhanced Selector**: Combines DOM selectors with computer vision for reliability
- **Real-Time Chatbot UI**: Web interface with live progress updates via WebSocket
- **Multi-Modal Selection**: DOM-based (fast) with vision fallback (robust)
- **Groq-Powered Planning**: Uses Groq's gpt-oss-120B for near-instant query processing
- **Intelligent Fallbacks**: JavaScript click/type fallbacks when standard methods fail

## 🏗️ Architecture

```
User Query + URL → Scraper → LLM Planner → Selector → Executor → Results
                      ↓           ↓            ↓          ↓
                   Snapshot  Semantic Steps  Candidates  Actions
```

### Components

1. **Scraper** (`src/scraper/fast_snapshot.py`): Playwright-based DOM snapshot generator
2. **Planner** (`src/planner/planner_agent.py`): Groq LLM converts queries to semantic steps
3. **Selector** (`src/selector/selector.py`): Multi-modal element selection (DOM + Vision)
4. **Executor** (`src/executor/executor.py`): Runs actions with validation and fallbacks
5. **Chatbot** (`chatbot/app.py`): FastAPI + WebSocket real-time interface

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Groq API Key (get free at [console.groq.com](https://console.groq.com))

### Installation

```bash
cd interactgen-agent

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set API key
export GROQ_API_KEY="your_key_here"  # Linux/Mac
$env:GROQ_API_KEY="your_key_here"     # Windows PowerShell
```

### Run Chatbot (Recommended)

```bash
# Linux/Mac
bash demo/start_chatbot.sh

# Windows
python chatbot/app.py
```

Open your browser to **http://localhost:5000**

### CLI Usage

```bash
# 1. Scrape a website
python src/scraper/fast_snapshot.py https://example.com snapshot.json

# 2. Generate steps from query
python src/planner/planner_agent.py \
  --query "Find the contact page" \
  --url https://example.com \
  --snapshot snapshot.json \
  --output steps.json

# 3. Select element candidates
python src/selector/selector.py snapshot.json steps.json --output candidates.json

# 4. Execute automation
python src/executor/executor.py snapshot.json steps.json candidates.json --output results.json
```

## 💡 Example Queries

Try these in the chatbot:

- **Google**: "Search for 'machine learning' and click the first result"
- **Wikipedia**: "Search for 'Artificial Intelligence' and read the summary"
- **Amazon**: "Find laptops under $1000"
- **GitHub**: "Search for 'web automation' repositories"

## 📁 Project Structure

```
interactgen-agent/
├── src/
│   ├── scraper/        # DOM snapshot generation
│   ├── planner/        # LLM query-to-steps conversion
│   ├── selector/       # Multi-modal element selection
│   ├── executor/       # Action execution with fallbacks
│   ├── orchestrator/   # Workflow coordination
│   └── utils/          # Schemas, selector history
├── chatbot/
│   ├── app.py          # FastAPI backend
│   └── static/         # Web UI (HTML/CSS/JS)
├── tests/              # Unit and integration tests
├── demo/               # Example queries and scripts
└── logs/               # Execution logs and history
```

## ⚙️ Configuration

Environment variables (optional):

```bash
GROQ_API_KEY=your_key_here          # Required
MAX_CANDIDATES=3                     # Max selector candidates to try
SNAPSHOT_WAIT_SEC=0.8                # Wait after page load
STEP_TIMEOUT_SEC=5                   # Max time per step
ACTION_TIMEOUT_MS=1500               #Timeout for actions
CHATBOT_HOST=localhost               # Chatbot server host
CHATBOT_PORT=5000                    # Chatbot server port
```

## 🧪 Testing

```bash
# Run all tests
pytest -v

# Run selector tests only
pytest tests/test_selector.py -v

# Run integration tests
pytest tests/test_end_to_end.py -v
```

## 🎯 How It Works

### 1. URL + Query Input
User provides website URL and natural language query in chatbot UI.

### 2. DOM Scraping
Playwright captures page snapshot with visible elements, bounding boxes, and generates 3-5 selector candidates per element (aria, id, class, text, xpath).

### 3. LLM Planning
Groq's gpt-oss-120B converts query into semantic steps with actions (click/type/navigate) and visual hints for element selection.

### 4. Selector Matching
Multi-modal approach:
- **DOM Strategy**: Scores candidates by provenance (aria > id > class > text)
- **Vision Strategy**: Uses bounding boxes and spatial reasoning (fallback)
- **Hybrid**: Combines both (60% DOM + 40% vision)

### 5. Execution
Tries top-3 candidates with fallbacks:
- Standard Playwright actions
- JavaScript click/type fallback
- Validation checks (presence/url/text)
- Screenshot on failure

### 6. Learning
Successful selectors stored in `logs/selector_history.json` for future scoring boost.

## 🔧 Advanced Features

### Selector Strategy Selection

```bash
# DOM-only (fastest)
python src/selector/selector.py snapshot.json steps.json --strategy dom

# Vision-based (most robust)
python src/selector/selector.py snapshot.json steps.json --strategy vision

# Hybrid (recommended)
python src/selector/selector.py snapshot.json steps.json --strategy hybrid
```

### Custom Actions

Supported actions in semantic steps:
- `navigate`: Go to URL
- `click`: Click element
- `type`: Type text into input
- `scroll`: Scroll up/down
- `extract`: Get text from element
- `wait`: Wait for condition

### Validators

Validation types for step verification:
- `presence`: Element exists
- `value_equals`: Input has specific value
- `url_contains`: URL contains substring
- `text_contains`: Page contains text

## 🚧 Limitations & Future Work

### Current Limitations
- Vision-based selector is simplified (full OCR + template matching not implemented)
- Async executor integration with chatbot UI is simplified
- Limited to Chromium browser

### Planned Improvements
- Full Tesseract OCR integration for vision selector
- OpenCV template matching for visual element detection
- Multi-browser support (Firefox, Safari)
- Session persistence and replay
- Browser extension for non-headless mode
- More sophisticated retry logic and error recovery

## 📝 License

MIT License - See LICENSE file

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 🙏 Acknowledgments

- **Groq** for fast LLM inference
- **Playwright** for browser automation
- **FastAPI** for modern web framework

## 📧 Support

For issues and questions, please open a GitHub issue.

---

**Built for the InteractGen Hackathon 2025** 🚀
