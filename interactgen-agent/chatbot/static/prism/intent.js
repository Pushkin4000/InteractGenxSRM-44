/**
 * Prism AI - Intent Engine
 * Interprets raw signals into user intent probabilities.
 */

class PrismIntentEngine {
    constructor() {
        this.intents = {
            explore: 0,   // Looking around
            construct: 0, // Typing / interacting
            monitor: 0,   // Watching progress
            frustration: 0 // Rage clicks etc
        };

        this.decayRate = 0.05; // 5% decay per tick
    }

    init() {
        console.log('🧠 Prism Intent: Initialized');

        // Listen for signals
        window.addEventListener('prism-signal', (e) => {
            this.processSignal(e.detail);
        });

        // Start decay loop
        setInterval(() => this.decay(), 500);
    }

    processSignal(signal) {
        switch (signal.type) {
            case 'high_velocity_mouse':
                this.intents.explore += 0.2;
                this.intents.monitor -= 0.1;
                break;
            case 'click':
                this.intents.construct += 0.3;
                break;
            case 'rage_click':
                this.intents.frustration += 1.0;
                break;
            case 'sustained_typing':
                this.intents.construct += 0.5;
                this.intents.explore -= 0.2;
                break;
        }

        this.clamp();
    }

    decay() {
        // Natural decay of intents over time
        for (let key in this.intents) {
            this.intents[key] = Math.max(0, this.intents[key] - this.decayRate);
        }

        // Passive 'Monitor' intent increases if nothing else is happening
        // (User is likely watching the automation)
        const totalActivity = this.intents.explore + this.intents.construct + this.intents.frustration;
        if (totalActivity < 0.2) {
            this.intents.monitor = Math.min(1, this.intents.monitor + 0.05);
        }
    }

    clamp() {
        for (let key in this.intents) {
            this.intents[key] = Math.min(1, Math.max(0, this.intents[key]));
        }
    }

    getTopIntent() {
        let top = 'monitor';
        let max = 0;

        for (let key in this.intents) {
            if (this.intents[key] > max) {
                max = this.intents[key];
                top = key;
            }
        }

        return { intent: top, confidence: max };
    }
}

window.PrismIntentEngine = PrismIntentEngine;
