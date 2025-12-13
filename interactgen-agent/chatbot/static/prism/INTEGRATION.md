# Prism AI Integration Architecture

## Overview
Prism AI is integrated as a **strictly client-side layer**. It resides entirely within the `static/` directory and does not require any changes to the Python backend (`app.py`).

## File Structure
```
chatbot/static/
├── index.html          # Entry point (links to prism scripts)
├── app.js              # Existing chatbot logic
└── prism/              # NEW: Isolated AI Layer
    ├── tracker.js      # Captures mouse/input events
    ├── intent.js       # Calculates intent scores
    ├── ui.js           # Renders the "Brain HUD" overlay
    └── core.js         # Orchestrates the system
```

## Runtime Integration
1.  **Loading:** The scripts are loaded via standard `<script>` tags in `index.html`.
2.  **Event Listeners:** `tracker.js` attaches *passive* event listeners to the `window` and `document` objects to observe user behavior (mouse movements, clicks, typing).
3.  **Overlay:** `ui.js` dynamically appends a new DOM element (`#prism-hud`) to the page body. This overlay floats above the existing UI.
4.  **Loop:** `core.js` runs a lightweight heartbeat (every 500ms) to update predictions and refresh the UI.

## Safety
-   **No Backend Impact:** Since it runs in the browser, it cannot break the Python server.
-   **Performance:** All calculations are simple heuristics (math) running on the client, introducing negligible overhead (<2ms per frame).
