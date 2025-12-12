// InteractGen - Split View Frontend

let ws = null;
let currentSessionId = null;
let currentUrl = '';

// DOM Elements
const urlInput = document.getElementById('url-input');
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');
const messages = document.getElementById('messages');
const taskList = document.getElementById('task-list');
const statusIndicator = document.getElementById('status-indicator');
const browserIframe = document.getElementById('browser-iframe');
const browserOverlay = document.getElementById('browser-overlay');
const urlDisplay = document.getElementById('url-display');

// Example chips click handler
document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
        urlInput.value = chip.dataset.url;
        queryInput.value = chip.dataset.query;
        queryInput.focus();
    });
});

// Send button handler
sendBtn.addEventListener('click', startAutomation);

// Enter key handler
queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        startAutomation();
    }
});

async function startAutomation() {
    const url = urlInput.value.trim();
    const query = queryInput.value.trim();

    // Validation
    if (!url || !query) {
        addMessage('error', 'Please enter both URL and query');
        return;
    }

    try {
        new URL(url);
    } catch (e) {
        addMessage('error', 'Please enter a valid URL (include https://)');
        return;
    }

    // Update UI state
    currentUrl = url;
    setRunning(true);

    // Clear previous tasks
    taskList.innerHTML = '';

    // Add initial task
    addTask('scrape', 'Scraping webpage', 'pending');
    addTask('plan', 'Generating steps', 'pending');
    addTask('select', 'Finding elements', 'pending');
    addTask('execute', 'Executing actions', 'pending');

    // Show iframe and update URL bar
    browserOverlay.classList.add('hidden');
    urlDisplay.value = url;

    // Load URL in iframe (for preview - actual automation happens server-side)
    try {
        browserIframe.src = url;
    } catch (e) {
        // Some sites block iframe embedding
        browserIframe.src = 'about:blank';
        addMessage('system', 'Note: Site blocks embedding. Automation runs in background browser.');
    }

    // Add user message
    addMessage('user', `🌐 ${url}\n💬 ${query}`);

    try {
        // Call API
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, query })
        });

        if (!response.ok) throw new Error('API request failed');

        const data = await response.json();
        currentSessionId = data.session_id;

        addMessage('agent', '🚀 Starting automation...');

        // Connect WebSocket
        connectWebSocket(currentSessionId);

    } catch (error) {
        addMessage('error', `Failed to start: ${error.message}`);
        setRunning(false);
    }
}

function connectWebSocket(sessionId) {
    if (ws) ws.close();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/${sessionId}`);

    ws.onopen = () => console.log('WebSocket connected');

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleUpdate(message);
    };

    ws.onerror = () => {
        addMessage('error', 'Connection error');
        setRunning(false);
    };

    ws.onclose = () => console.log('WebSocket closed');
}

function handleUpdate(message) {
    if (message.type !== 'update') return;

    const update = message.data;
    const status = update.status;

    // Update tasks based on status
    switch (status) {
        case 'running':
        case 'scraping':
            updateTask('scrape', 'running', 'Loading page...');
            break;
        case 'scraped':
            updateTask('scrape', 'success', update.message);
            updateTask('plan', 'running', 'Analyzing query...');
            break;
        case 'planning':
            updateTask('plan', 'running', 'Generating automation steps...');
            break;
        case 'planned':
            updateTask('plan', 'success', `Generated ${update.steps?.length || 0} steps`);
            updateTask('select', 'running', 'Finding elements...');
            // Show steps if available
            if (update.steps) {
                showSteps(update.steps);
            }
            break;
        case 'selecting':
            updateTask('select', 'running', 'Matching selectors...');
            break;
        case 'selected':
            updateTask('select', 'success', update.message);
            updateTask('execute', 'running', 'Starting execution...');
            break;
        case 'executing':
            updateTask('execute', 'running', 'Running automation...');
            break;
        case 'executing_step':
            updateTask('execute', 'running', update.message);
            addMessage('agent', `⚡ ${update.message}`);
            break;
        case 'step_complete':
            if (update.result?.ok) {
                addMessage('success', `✓ ${update.result.step_id} completed`);
            } else {
                addMessage('error', `✗ ${update.result?.step_id} failed`);
            }
            break;
        case 'completed':
            updateTask('execute', 'success', 'All steps completed!');
            addMessage('success', `🎉 ${update.message}`);
            setRunning(false);
            break;
        case 'failed':
            updateTask('execute', 'failed', update.message);
            addMessage('error', `❌ ${update.message}`);
            setRunning(false);
            break;
    }
}

function addTask(id, title, status) {
    const icons = {
        pending: '○',
        running: '◐',
        success: '✓',
        failed: '✗'
    };

    const task = document.createElement('div');
    task.className = `task-item ${status}`;
    task.id = `task-${id}`;
    task.innerHTML = `
        <span class="task-icon">${icons[status]}</span>
        <div class="task-content">
            <div class="task-title">${title}</div>
            <div class="task-detail"></div>
        </div>
    `;
    taskList.appendChild(task);
}

function updateTask(id, status, detail = '') {
    const task = document.getElementById(`task-${id}`);
    if (!task) return;

    const icons = {
        pending: '○',
        running: '◐',
        success: '✓',
        failed: '✗'
    };

    task.className = `task-item ${status}`;
    task.querySelector('.task-icon').textContent = icons[status];
    if (detail) {
        task.querySelector('.task-detail').textContent = detail;
    }
}

function showSteps(steps) {
    // Add step tasks
    steps.forEach((step, idx) => {
        const stepId = step.step_id || `step-${idx + 1}`;
        const title = `${step.action}: ${step.target || 'N/A'}`;

        // Check if step task already exists
        if (!document.getElementById(`task-${stepId}`)) {
            addTask(stepId, title, 'pending');
        }
    });
}

function addMessage(type, content) {
    const msg = document.createElement('div');
    msg.className = `message ${type}`;
    msg.textContent = content;
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
}

function setRunning(running) {
    sendBtn.disabled = running;

    if (running) {
        sendBtn.innerHTML = '<span class="btn-icon">⟳</span> Running...';
        sendBtn.classList.add('running');
        statusIndicator.textContent = '● Running';
        statusIndicator.className = 'status-indicator running';
    } else {
        sendBtn.innerHTML = '<span class="btn-icon">▶</span> Run Automation';
        sendBtn.classList.remove('running');
        statusIndicator.textContent = '● Ready';
        statusIndicator.className = 'status-indicator';
    }
}
