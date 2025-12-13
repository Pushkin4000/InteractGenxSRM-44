/**
 * Prism AI - Behavior Tracker
 * Monitors raw user actions and converts them into "Signals".
 */

class PrismTracker {
    constructor() {
        this.signals = [];
        this.lastMousePos = { x: 0, y: 0 };
        this.lastClickTime = 0;
        this.clickCount = 0;
        this.typingStart = 0;
        this.keystrokes = 0;
    }

    init() {
        console.log('👁️ Prism Tracker: Initialized');
        this.attachListeners();
    }

    attachListeners() {
        // Track Mouse Velocity & Hesitation
        let throttle;
        document.addEventListener('mousemove', (e) => {
            if (throttle) return;
            throttle = setTimeout(() => {
                this.analyzeMouse(e);
                throttle = null;
            }, 100);
        }, { passive: true });

        // Track Clicks (Rage Click Detection)
        document.addEventListener('click', (e) => {
            this.analyzeClick(e);
        }, { passive: true });

        // Track Typing (Engagement)
        const inputs = document.querySelectorAll('input, textarea');
        inputs.forEach(input => {
            input.addEventListener('keydown', () => this.analyzeTyping());
        });
    }

    analyzeMouse(e) {
        // Calculate velocity
        const dx = e.clientX - this.lastMousePos.x;
        const dy = e.clientY - this.lastMousePos.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        this.lastMousePos = { x: e.clientX, y: e.clientY };

        // High velocity = Skimming/Exploring
        if (distance > 100) {
            this.emit('high_velocity_mouse');
        }

        // TODO: Detect "Hesitation" (hovering over element for >1s)
    }

    analyzeClick(e) {
        const now = Date.now();
        if (now - this.lastClickTime < 300) {
            this.clickCount++;
            if (this.clickCount >= 3) {
                this.emit('rage_click');
            }
        } else {
            this.clickCount = 1;
        }
        this.lastClickTime = now;
        this.emit('click');
    }

    analyzeTyping() {
        const now = Date.now();
        if (now - this.typingStart > 2000) {
            // Reset if pause is long
            this.typingStart = now;
            this.keystrokes = 0;
        }
        this.keystrokes++;

        // Fast typing = Intent to Construct
        if (this.keystrokes > 5) {
            this.emit('sustained_typing');
        }
    }

    emit(signalType, data = {}) {
        // In a real system, this would dispatch to the Event Bus
        // For MVP, we'll store it in a global state or dispatch a custom event
        const event = new CustomEvent('prism-signal', {
            detail: { type: signalType, timestamp: Date.now(), ...data }
        });
        window.dispatchEvent(event);

        // Visual debug (temporary)
        // console.log(`📡 Signal: ${signalType}`);
    }
}

// Export for global usage
window.PrismTracker = PrismTracker;
