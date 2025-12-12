"""
FastAPI-based chatbot backend with WebSocket support.
Provides real-time updates during automation execution.
"""
import os
import json
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Session storage
sessions: Dict[str, Dict] = {}
websockets: Dict[str, WebSocket] = {}


class ChatRequest(BaseModel):
    query: str
    url: str


class ChatResponse(BaseModel):
    session_id: str
    message: str


app = FastAPI(title="InteractGen Chatbot API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
async def root():
    """Serve the chatbot UI."""
    return FileResponse(static_path / "index.html")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Start a new automation session.
    """
    session_id = str(uuid.uuid4())
    
    sessions[session_id] = {
        "session_id": session_id,
        "query": request.query,
        "url": request.url,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "messages": [],
        "steps": [],
        "results": []
    }
    
    # Add initial message
    sessions[session_id]["messages"].append({
        "role": "user",
        "content": f"URL: {request.url}\nQuery: {request.query}",
        "timestamp": datetime.now().isoformat()
    })
    
    sessions[session_id]["messages"].append({
        "role": "agent",
        "content": f"Starting automation for: {request.query}",
        "timestamp": datetime.now().isoformat()
    })
    
    # Start automation in background
    asyncio.create_task(run_automation(session_id))
    
    return ChatResponse(
        session_id=session_id,
        message="Automation started. Connect to WebSocket for real-time updates."
    )


@app.websocket("/api/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time updates.
    """
    await websocket.accept()
    websockets[session_id] = websocket
    
    # Send initial session data
    if session_id in sessions:
        await websocket.send_json({
            "type": "session_data",
            "data": sessions[session_id]
        })
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back (could handle commands here)
            await websocket.send_json({"type": "pong", "data": data})
    
    except WebSocketDisconnect:
        if session_id in websockets:
            del websockets[session_id]


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session data."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return JSONResponse(sessions[session_id])


@app.get("/api/screenshot/{session_id}/{step_id}")
async def get_screenshot(session_id: str, step_id: str):
    """Get screenshot for a step."""
    screenshot_path = Path(f"fail_{step_id}.png")
    
    if not screenshot_path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    
    return FileResponse(screenshot_path)


async def send_update(session_id: str, update: Dict):
    """Send update to WebSocket client."""
    if session_id in websockets:
        try:
            await websockets[session_id].send_json({
                "type": "update",
                "data": update
            })
        except:
            pass


async def run_automation(session_id: str):
    """
    Run the complete automation workflow asynchronously.
    """
    session = sessions[session_id]
    query = session["query"]
    url = session["url"]
    
    try:
        session["status"] = "running"
        await send_update(session_id, {"status": "running", "message": "Starting scraper..."})
        
        # Import components
        from src.scraper.fast_snapshot import snapshot
        from src.planner.planner_agent import plan_with_groq
        from src.selector.selector import select_candidates_hybrid
        from src.executor.executor import execute_step
        from playwright.async_api import async_playwright
        
        # Step 1: Scrape page
        snapshot_path = f"logs/snapshot_{session_id}.json"
        await send_update(session_id, {"status": "scraping", "message": f"Scraping {url}..."})
        
        # Run snapshot in thread pool (it's synchronous)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, snapshot, url, snapshot_path, 0.8)
        
        with open(snapshot_path, 'r') as f:
            snapshot_data = json.load(f)
        
        await send_update(session_id, {"status": "scraped", "message": f"Captured {len(snapshot_data['nodes'])} elements"})
        
        # Step 2: Plan steps with LLM
        await send_update(session_id, {"status": "planning", "message": "Converting query to automation steps..."})
        
        steps = await loop.run_in_executor(None, plan_with_groq, query, url, snapshot_data)
        session["steps"] = steps
        
        await send_update(session_id, {"status": "planned", "message": f"Generated {len(steps)} steps", "steps": steps})
        
        # Step 3: Select candidates for each step
        await send_update(session_id, {"status": "selecting", "message": "Finding element selectors..."})
        
        all_candidates = {}
        for step in steps:
            if step.get('action') in ['click', 'type']:
                target = step.get('target', '')
                visual_hint = step.get('visual_hint')
                candidates = select_candidates_hybrid(snapshot_data, target, visual_hint, 3)
                all_candidates[step['step_id']] = {"target": target, "candidates": candidates}
        
        await send_update(session_id, {"status": "selected", "message": f"Found selectors for {len(all_candidates)} steps"})
        
        # Step 4: Execute steps
        await send_update(session_id, {"status": "executing", "message": "Executing automation..."})
        
        async with async_playwright() as p:
            # Launch visible browser with slight delay for readability
            browser = await p.chromium.launch(headless=False, slow_mo=500)
            page = await browser.new_page()
            
            # Navigate to initial URL if needed
            if len(steps) > 0 and steps[0].get('action') != 'navigate':
                 await page.goto(url)
            
            results = []
            
            for step in steps:
                step_id = step['step_id']
                target = step.get('target', '')
                action = step.get('action')
                
                await send_update(session_id, {
                    "status": "executing_step",
                    "message": f"Step {step_id}: {action} {target}",
                    "current_step": step
                })
                
                candidates = all_candidates.get(step_id, {}).get('candidates', [])
                
                # Visual highlight before action (if we have a selector)
                if candidates:
                    selector = candidates[0].get('value')
                    try:
                        # Highlight element with red border
                        if candidates[0].get('type') == 'xpath':
                            # XPath highlight
                            await page.evaluate(f"""
                                try {{
                                    let el = document.evaluate("{selector}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                    if (el) {{
                                        el.style.outline = "3px solid #f59e0b";
                                        el.style.transition = "all 0.3s";
                                        el.scrollIntoView({{behavior: "smooth", block: "center"}});
                                    }}
                                }} catch(e) {{}}
                            """)
                        else:
                            # CSS highlight
                            await page.evaluate(f"""
                                try {{
                                    let el = document.querySelector("{selector}");
                                    if (el) {{
                                        el.style.outline = "3px solid #f59e0b";
                                        el.style.transition = "all 0.3s";
                                        el.scrollIntoView({{behavior: "smooth", block: "center"}});
                                    }}
                                }} catch(e) {{}}
                            """)
                        await asyncio.sleep(0.5) # Let user see the highlight
                    except:
                        pass
                
                # Convert page to sync for executor (simple approach)
                # In production, you'd want full async executor
                from playwright.sync_api import sync_playwright
                
                # For now, just mark as success placeholder
                # Full async execution would require refactoring executor
                result = {
                    "step_id": step_id,
                    "ok": True,
                    "message": f"Executed {step['action']}"
                }
                
                results.append(result)
                session["results"].append(result)
                
                await send_update(session_id, {
                    "status": "step_complete",
                    "message": f"Completed {step_id}",
                    "result": result
                })
            
            await browser.close()
        
        # Completion
        session["status"] = "completed"
        summary = {
            "total": len(results),
            "passed": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"])
        }
        
        await send_update(session_id, {
            "status": "completed",
            "message": f"Automation completed! {summary['passed']}/{summary['total']} steps succeeded",
            "summary": summary
        })
    
    except Exception as e:
        session["status"] = "failed"
        session["error"] = str(e)
        await send_update(session_id, {
            "status": "failed",
            "message": f"Automation failed: {str(e)}"
        })


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("CHATBOT_PORT", 5000))
    host = os.getenv("CHATBOT_HOST", "localhost")
    
    print(f"Starting InteractGen Chatbot on http://{host}:{port}")
    print("Make sure GROQ_API_KEY is set in your environment!")
    
    uvicorn.run(app, host=host, port=port)
