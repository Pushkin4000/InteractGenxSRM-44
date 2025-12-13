import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.append(r"d:\Project\Hackathon\InteractGenxSRM-44\interactgen-agent")

from src.executor.async_executor import execute_step_async

async def run_tests():
    print("Starting tests...")
    
    # --- Test 1: Click Retry ---
    print("\n--- Test 1: Click Retry ---")
    dom = {
        "nodes": [
            {
                "node_id": "n1",
                "tag": "button",
                "text": "Submit",
                "candidates": [
                    {"type": "css", "value": "#primary-btn", "score": 0.9},
                    {"type": "css", "value": ".submit-btn", "score": 0.8}
                ],
                "xpath": "//button[text()='Submit']"
            }
        ]
    }
    
    page = AsyncMock()
    # Mocking standard click
    # 1. click(#primary-btn) -> Fail
    # 2. click(.submit-btn) -> Success
    page.click.side_effect = [Exception("Timeout"), None]
    
    # Mocking evaluate (JS click)
    # 1. evaluate(#primary-btn) -> False (Fail)
    # 2. evaluate(.submit-btn) -> True (Success - though standard click works so this wont be called)
    page.evaluate.side_effect = [False, True] 
    
    # Wait: execute_step_async calls evaluate for JS fallback if click fails.
    # Logic:
    # 1. Try candidates[0] (#primary-btn):
    #    - await page.click(...) -> Fails (Timeout)
    #    - await page.evaluate(js...) -> Fails (returns False)
    #    -> Loop continues
    # 2. Try candidates[1] (.submit-btn):
    #    - await page.click(...) -> Success (None)
    #    -> Break, Success
    
    step = {
        "action": "click",
        "target": "Submit button",
        "element_id": "n1"
    }
    
    result = await execute_step_async(page, step, dom)
    print(f"Result 1: {result}")
    
    # We expect 2 calls to click (one fail, one success)
    # AND 1 call to evaluate (failed JS fallback for first candidate)
    if result['ok'] and page.click.call_count == 2:
        print("PASS: Click retried with second candidate and succeeded.")
    else:
        print(f"FAIL: ok={result['ok']}, click_count={page.click.call_count}, eval_count={page.evaluate.call_count}")
        print(f"Message: {result['message']}")

    # --- Test 2: JS Fallback ---
    print("\n--- Test 2: JS Fallback ---")
    dom2 = {
        "nodes": [
            {
                "node_id": "n1", 
                "tag": "button",
                "candidates": [
                    {"type": "css", "value": "#btn", "score": 0.9}
                ]
            }
        ]
    }
    
    page2 = AsyncMock()
    # Click always fails
    page2.click.side_effect = Exception("Click Intercepted")
    # Evaluate (JS click) succeeds
    page2.evaluate.return_value = True
    
    step2 = {
        "action": "click",
        "target": "Submit button",
        "element_id": "n1"
    }
    
    result2 = await execute_step_async(page2, step2, dom2)
    print(f"Result 2: {result2}")
    
    if result2['ok'] and "JS" in result2['message']:
        print("PASS: JS fallback worked.")
    else:
        print(f"FAIL: ok={result2['ok']}, message={result2['message']}")

if __name__ == "__main__":
    asyncio.run(run_tests())
