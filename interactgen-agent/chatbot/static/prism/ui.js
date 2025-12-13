/**
 * Prism AI - UI Visualization (Brain HUD)
 * Renders the predictive layer overlay.
 */

class PrismUI {
    constructor() {
        this.container = null;
    }

    init() {
        console.log('🎨 Prism UI: Initialized');
        this.injectStyles();
        this.createOverlay();

        // Listen for signals to visualize them
        window.addEventListener('prism-signal', (e) => {
            this.logSignal(e.detail.type);
        });
    }

    injectStyles() {
        const style = document.createElement('style');
        style.textContent = `
            #prism-hud {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 250px;
                background: rgba(0, 0, 0, 0.85);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 15px;
                color: #fff;
                font-family: 'Segoe UI', monospace;
                font-size: 12px;
                z-index: 9999;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                transition: opacity 0.3s;
            }
            #prism-hud h3 {
                margin: 0 0 10px 0;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #888;
                display: flex;
                justify-content: space-between;
            }
            .prism-status {
                display: flex;
                align-items: center;
                margin-bottom: 10px;
            }
            .prism-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #555;
                margin-right: 8px;
                box-shadow: 0 0 5px currentColor;
            }
            .prism-intent {
                font-size: 16px;
                font-weight: bold;
                text-transform: capitalize;
            }
            .prism-bars {
                margin-top: 10px;
            }
            .prism-bar-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 4px;
            }
            .prism-track {
                width: 100%;
                height: 4px;
                background: #333;
                border-radius: 2px;
                overflow: hidden;
            }
            .prism-fill {
                height: 100%;
                background: #4caf50;
                width: 0%;
                transition: width 0.3s;
            }
            .prism-log {
                margin-top: 10px;
                height: 60px;
                overflow: hidden;
                border-top: 1px solid #333;
                padding-top: 5px;
                opacity: 0.7;
            }
            .log-item {
                font-size: 10px;
                color: #aaa;
                margin-bottom: 2px;
                animation: fadeIn 0.3s;
            }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        `;
        document.head.appendChild(style);
    }

    createOverlay() {
        this.container = document.createElement('div');
        this.container.id = 'prism-hud';
        this.container.innerHTML = `
            <h3>Prism AI Layer <span style="color:#4caf50">● LIVE</span></h3>
            <div class="prism-status">
                <div class="prism-dot" id="prism-pulse" style="color:#555"></div>
                <div class="prism-intent" id="prism-intent-text">Calibrating...</div>
            </div>
            
            <div class="prism-bars" id="prism-bars">
                <!-- Bars injected dynamically -->
            </div>

            <div class="prism-log" id="prism-log">
                <!-- Logs here -->
            </div>
        `;
        document.body.appendChild(this.container);
    }

    update(intents, topIntent) {
        // Update Main Status
        const textEl = document.getElementById('prism-intent-text');
        const pulseEl = document.getElementById('prism-pulse');
        const barsEl = document.getElementById('prism-bars');

        if (textEl) {
            textEl.textContent = topIntent.intent;

            // Color coding
            const colors = {
                explore: '#2196f3',    // Blue
                construct: '#ff9800',  // Orange
                monitor: '#4caf50',    // Green
                frustration: '#f44336' // Red
            };
            const color = colors[topIntent.intent] || '#fff';

            textEl.style.color = color;
            pulseEl.style.backgroundColor = color;
            pulseEl.style.color = color; // for shadow
        }

        // Update Bars
        if (barsEl) {
            barsEl.innerHTML = Object.entries(intents).map(([key, val]) => `
                <div class="prism-bar-row">
                    <span style="width: 70px; opacity: 0.8">${key}</span>
                    <div class="prism-track">
                        <div class="prism-fill" style="width: ${val * 100}%; background: ${this.getColor(key)}"></div>
                    </div>
                </div>
            `).join('');
        }
    }

    getColor(intent) {
        const colors = {
            explore: '#2196f3',
            construct: '#ff9800',
            monitor: '#4caf50',
            frustration: '#f44336'
        };
        return colors[intent] || '#888';
    }

    logSignal(type) {
        const logEl = document.getElementById('prism-log');
        if (!logEl) return;

        const item = document.createElement('div');
        item.className = 'log-item';
        item.textContent = `> detected: ${type}`;
        logEl.prepend(item);

        if (logEl.children.length > 5) {
            logEl.removeChild(logEl.lastChild);
        }
    }
}

window.PrismUI = PrismUI;
