
import sys
import os
import json

# Add project root to path
sys.path.append(r"d:\Project\Hackathon\InteractGenxSRM-44\interactgen-agent")

try:
    from src.executor.async_executor import find_best_selector
    print("Successfully imported find_best_selector")
except ImportError as e:
    print(f"Failed to import find_best_selector: {e}")
    sys.exit(1)

# Dummy DOM
dom = {
    "nodes": [
        {
            "node_id": "n1",
            "tag": "button",
            "text": "Submit Form", 
            "candidates": [
                {"type": "css", "value": "#submit-btn", "score": 0.9}
            ]
        },
        {
            "node_id": "n2", 
            "tag": "input",
            "attributes": {"name": "email"},
            "candidates": []
        }
    ]
}

# Test 1: Exact match via candidate
sel1 = find_best_selector("Submit Form", dom)
print(f"Test 1 (Submit Form): {sel1} (Expect #submit-btn)")

# Test 2: Attribute match fallback
sel2 = find_best_selector("email field", dom)
print(f"Test 2 (email field): {sel2}") 
# Note: fallback logic might require specific mocking if fuzzy_match is complex, 
# but let's see if it runs without crashing.

