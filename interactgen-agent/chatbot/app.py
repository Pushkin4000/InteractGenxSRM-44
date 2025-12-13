"""
FastAPI-based chatbot backend with WebSocket support.
Provides real-time updates during automation execution.
"""
import os
import json
import uuid
import asyncio
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import sys
# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Load environment variables from .env file
# Look for .env in the interactgen-agent directory (parent of chatbot/)
env_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path=env_path)
# Also try loading from current directory as fallback
load_dotenv()


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
    Run automation with REAL-TIME iterative execution.
    
    New approach:
    1. Launch visible browser
    2. Loop: Fast DOM scrape → Plan ONE step → Highlight → Execute → Repeat
    3. User sees every action happening live
    """
    session = sessions[session_id]
    query = session["query"]
    url = session["url"]
    
    # Get API key early and validate
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print(f"❌ [{session_id}] GROQ_API_KEY missing!")
        session["status"] = "failed"
        session["error"] = "GROQ_API_KEY not set. Please set it in .env file or environment variable."
        await send_update(session_id, {
            "status": "failed",
            "message": "❌ Error: GROQ_API_KEY not found. Please set it in .env file or environment variable."
        })
        return
    
    try:
        print(f"🚀 [{session_id}] Starting automation for: {url}")
        session["status"] = "running"
        await send_update(session_id, {
            "status": "starting", 
            "message": "🚀 Launching browser (visible mode)..."
        })
        
        # Import NEW fast components
        from src.scraper.fast_dom_extractor import extract_dom_fast, highlight_element, remove_highlight
        from src.planner.planner_agent import plan_next_step
        from src.executor.async_executor import execute_step_async, find_best_selector
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            print(f"  [{session_id}] Launching browser...")
            # Launch VISIBLE browser so user can interact if needed
            browser = await p.chromium.launch(
                headless=False,  # Visible browser for user interaction
                slow_mo=200  # 0.2s delay - much faster but still visible
            )
            page = await browser.new_page()
            
            # Set viewport size
            await page.set_viewport_size({"width": 1280, "height": 800})
            
            # Navigate to URL
            print(f"  [{session_id}] Navigating to {url}...")
            await send_update(session_id, {
                "status": "navigating", 
                "message": f"📍 Opening {url}..."
            })
            
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=45000)
                # Wait for at least some content to render
                try:
                    await page.wait_for_selector('body', timeout=5000)
                except:
                    pass
            except Exception as e:
                print(f"  [{session_id}] Navigation warning: {e}")
                await send_update(session_id, {
                    "status": "error",
                    "message": f"⚠️ Navigation warning: {str(e)} (continuing anyway)"
                })
            
            await asyncio.sleep(0.5)  # Minimal wait for page stability
            
            # Send initial screenshot
            try:
                screenshot_bytes = await page.screenshot(type='jpeg', quality=75)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                await send_update(session_id, {
                    "status": "screenshot",
                    "screenshot": screenshot_b64,
                    "url": page.url,
                    "message": "Page loaded"
                })
            except Exception as e:
                print(f"Screenshot error: {e}")
            
            executed_steps = []
            max_steps = 20  # Increased limit
            step_count = 0
            consecutive_failures = 0
            max_consecutive_failures = 5  # Stop if 5 steps fail in a row
            seen_actions = []  # Track recent actions to detect loops
            last_url = url  # Track URL changes
            
            print(f"  [{session_id}] Starting loop...")
            while step_count < max_steps:
                step_count += 1
                print(f"  [{session_id}] Step {step_count}: Analyzing...")
                
                # === STEP 1: Fast DOM Extraction (~50-100ms) ===
                if step_count == 1:
                    await send_update(session_id, {
                        "status": "analyzing",
                        "message": f"🔍 Analyzing page..."
                    })
                
                current_dom = await extract_dom_fast(page)
                # DO NOT filter nodes here - let the planner handle selection
                # We need to pass the FULL DOM to the planner so it can find things
                
                # === STEP 2: Plan NEXT single step ===
                # Skip status update for speed - only on first step
                if step_count <= 2:
                    await send_update(session_id, {
                        "status": "planning",
                        "message": "🤔 Planning..."
                    })
                
                print(f"  [{session_id}] Planning next step...")
                # Run LLM in thread pool (it's synchronous)
                # Pass API key explicitly to ensure it's available in the executor thread
                loop = asyncio.get_event_loop()
                try:
                    next_step = await loop.run_in_executor(
                        None, 
                        plan_next_step, 
                        query, 
                        page.url,  # Use current URL (may have changed)
                        current_dom, 
                        executed_steps,
                        api_key  # Explicitly pass API key
                    )
                except Exception as e:
                    error_str = str(e).lower()
                    print(f"  [{session_id}] Planning error: {e}")
                    
                    # Check for API rate limit errors
                    if 'rate limit' in error_str or '429' in error_str or 'quota' in error_str:
                        await send_update(session_id, {
                            "status": "error",
                            "message": "⚠️ API rate limit reached. Waiting 10 seconds..."
                        })
                        await asyncio.sleep(10)  # Wait before retrying
                        next_step = {"action": "wait", "target": "", "value": "", "reason": "Rate limit wait"}
                    else:
                        await send_update(session_id, {
                            "status": "error",
                            "message": f"❌ Planning error: {str(e)[:50]}"
                        })
                        next_step = {"action": "wait", "target": "", "value": "", "reason": f"Error: {str(e)[:30]}"}
                
                print(f"  [{session_id}] Planned: {next_step.get('action')} {next_step.get('target')}")
                
                # Check if done - require at least 2 successful steps to prevent premature completion
                if next_step.get('action') == 'done':
                    successful_steps = sum(1 for s in executed_steps if s.get('result', {}).get('ok'))
                    if successful_steps >= 2:
                        reason = next_step.get('reason', 'Task complete')
                        print(f"  [{session_id}] DONE: {reason}")
                        await send_update(session_id, {
                            "status": "done",
                            "message": f"✅ Task complete: {reason}",
                            "step": next_step
                        })
                        break
                    else:
                        # Too early to be done - continue
                        print(f"  [{session_id}] Ignoring premature 'done' (0 successful steps)")
                        next_step = {"action": "wait", "target": "", "value": "", "reason": "Too early"}
                
                # Loop detection: Check if we're repeating the same action
                action_key = f"{next_step.get('action')}:{next_step.get('target', '')[:30]}"
                seen_actions.append(action_key)
                if len(seen_actions) > 3:
                    seen_actions.pop(0)  # Keep only last 3
                
                # If same action repeated 3 times, force a different action
                if len(seen_actions) >= 3 and len(set(seen_actions)) == 1:
                    print(f"  [{session_id}] ⚠️ LOOP DETECTED: Repeating same action '{action_key}'")
                    await send_update(session_id, {
                        "status": "warning",
                        "message": f"⚠️ Detected loop - trying different approach"
                    })
                    # Force a scroll or wait to break the loop
                    next_step = {"action": "scroll", "target": "", "value": "down"}
                    seen_actions = []  # Reset
                
                # Handle wait action from planner (errors, rate limits, etc)
                # REMOVED: continue statement was causing infinite loops
                # Instead, wait actions are now properly executed and tracked

                
                # Store step info (skip verbose status update for speed)
                session["steps"].append(next_step)
                
                # === STEP 3: Find Selector and Execute ===
                target = next_step.get('target', '')
                action = next_step.get('action', '')
                
                # Skip highlighting for speed - just execute
                selector = find_best_selector(target, current_dom)
                
                # If no selector found, try to find by text/aria more aggressively
                if not selector and target:
                    for node in current_dom.get('nodes', []):
                        node_text = (node.get('text') or '').lower()
                        node_aria = (node.get('aria_label') or '').lower()
                        target_lower = target.lower()
                        if target_lower in node_text or target_lower in node_aria or node_text in target_lower:
                            candidates = node.get('candidates', [])
                            if candidates:
                                selector = candidates[0].get('value')
                                break
                            elif node.get('xpath'):
                                selector = node.get('xpath')
                                break
                
                # Update step with selector for better execution
                if selector:
                    next_step['selector'] = selector
                    log_msg = f"⚡ {action} '{target[:30]}' using {selector[:40]}"
                else:
                    log_msg = f"⚡ {action} '{target[:30]}' (no selector found)"
                
                print(f"  [{session_id}] Executing: {log_msg}")
                await send_update(session_id, {
                    "status": "executing",
                    "message": log_msg,
                    "selector": selector
                })
                
                result = await execute_step_async(page, next_step, current_dom)
                
                # Record result
                executed_steps.append({"step": next_step, "result": result})
                session["results"].append(result)
                
                if result.get('ok'):
                    print(f"  [{session_id}] Step success")
                    consecutive_failures = 0  # Reset failure counter
                    await send_update(session_id, {
                        "status": "step_success",
                        "message": f"✓ {result.get('message', 'Success')[:60]}",
                        "result": result
                    })
                else:
                    consecutive_failures += 1
                    print(f"  [{session_id}] Step failed ({consecutive_failures}/{max_consecutive_failures}): {result.get('message')}")
                    await send_update(session_id, {
                        "status": "step_failed",
                        "message": f"✗ {result.get('message', 'Failed')[:60]}",
                        "result": result
                    })
                    
                    # Stop if too many consecutive failures
                    if consecutive_failures >= max_consecutive_failures:
                        print(f"  [{session_id}] ⚠️ Too many consecutive failures, stopping")
                        await send_update(session_id, {
                            "status": "failed",
                            "message": f"⚠️ Stopped: {consecutive_failures} consecutive failures. Task may be stuck."
                        })
                        break
                
                # Check if URL changed (indicates progress)
                current_url = page.url
                if current_url != last_url:
                    print(f"  [{session_id}] URL changed: {last_url} -> {current_url}")
                    last_url = current_url
                    seen_actions = []  # Reset loop detection on URL change
                
                # Wait for any page transitions after action (non-blocking)
                try:
                    await asyncio.wait_for(
                        page.wait_for_load_state('domcontentloaded', timeout=800),
                        timeout=1.0
                    )
                except:
                    pass  # Continue anyway - don't block
                
                # Send screenshot only every 3rd step or on failures (reduce latency)
                if step_count % 3 == 0 or not result.get('ok'):
                    try:
                        screenshot_bytes = await page.screenshot(type='jpeg', quality=60)
                        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                        await send_update(session_id, {
                            "status": "screenshot",
                            "screenshot": screenshot_b64,
                            "url": page.url
                        })
                    except:
                        pass  # Don't block on screenshot errors
                
                # Minimal pause for speed
                await asyncio.sleep(0.1)
                
                # Debug: Confirm we reached end of loop iteration
                print(f"  [{session_id}] === End of step {step_count}, continuing to next iteration ===")
            
            # Don't close browser immediately - keep it open for user to see
            # User can close it manually or we'll close it after a delay
            await send_update(session_id, {
                "status": "browser_open",
                "message": "🌐 Browser kept open for inspection. It will close automatically in 30 seconds."
            })
            
            # Keep browser open for 30 seconds, then close
            await asyncio.sleep(30)
            try:
                await browser.close()
            except:
                pass
        
        # Final summary
        session["status"] = "completed"
        total = len(executed_steps)
        passed = sum(1 for s in executed_steps if s.get('result', {}).get('ok'))
        
        await send_update(session_id, {
            "status": "completed",
            "message": f"🎉 Automation complete! {passed}/{total} steps succeeded",
            "summary": {"total": total, "passed": passed, "failed": total - passed}
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        session["status"] = "failed"
        session["error"] = str(e)
        print(f"❌ [{session_id}] Fatal Error: {e}")
        await send_update(session_id, {
            "status": "failed",
            "message": f"❌ Error: {str(e)}"
        })


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("CHATBOT_PORT", 5000))
    host = os.getenv("CHATBOT_HOST", "localhost")
    
    # Validate API key is available
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("=" * 60)
        print("❌ ERROR: GROQ_API_KEY not found!")
        print("=" * 60)
        print("Please set your API key using one of these methods:")
        print("\n1. Create a .env file in interactgen-agent/ with:")
        print("   GROQ_API_KEY=your_key_here")
        print("\n2. Or set environment variable:")
        print("   Windows PowerShell: $env:GROQ_API_KEY='your_key_here'")
        print("   Linux/Mac: export GROQ_API_KEY='your_key_here'")
        print("\nGet your free API key at: https://console.groq.com")
        print("=" * 60)
        exit(1)
    
    print(f"Starting InteractGen Chatbot on http://{host}:{port}")
    print(f"✓ GROQ_API_KEY found (starts with: {api_key[:10]}...)")
    
    uvicorn.run(app, host=host, port=port)
