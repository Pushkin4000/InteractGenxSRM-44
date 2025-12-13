/**
 * Prism AI - Core Orchestrator
 * Bootstraps the system and ties components together.
 */

class PrismCore {
    constructor() {
        this.tracker = new PrismTracker();
        this.intentEngine = new PrismIntentEngine();
        this.ui = new PrismUI();
        this.running = false;
    }

    start() {
        if (this.running) return;
        console.log('🔮 Prism AI: Starting...');

        // Initialize components
        this.tracker.init();
        this.intentEngine.init();
        this.ui.init();

        this.running = true;
        this.loop();
    }

    loop() {
        if (!this.running) return;

        // 1. Get current intent state from Engine
        const currentIntents = this.intentEngine.intents;
        const topIntent = this.intentEngine.getTopIntent();

        // 2. Update UI
        this.ui.update(currentIntents, topIntent);

        // 3. Loop (Simulate 5Hz update rate)
        requestAnimationFrame(() => {
            setTimeout(() => this.loop(), 200);
        });
    }
}

// Global Bootstrap
window.Prism = new PrismCore();

// Auto-start when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Small delay to ensure other scripts loaded
    setTimeout(() => {
        window.Prism.start();
    }, 500);
});
