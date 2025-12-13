import asyncio
import sys
import hashlib
from unittest.mock import AsyncMock, MagicMock

# Define dummy result first to avoid ImportErrors before mocking modules
result_mock = {'ok': True, 'message': 'Clicked'}

async def test_loop_detection():
    print("Starting Loop Detection Verification...")
    
    # Mock data
    session_id = "test-session"
    step_count = 1
    state_hash = "abc12345"
    
    # Mock Page
    page = AsyncMock()
    
    # Mock execute_step_async to succeed
    async def mock_execute(p, s, d):
        return {'ok': True, 'message': 'Clicked'}
        
    # Mock extract_dom_fast to return SAME DOM (No-Op scenario)
    async def mock_extract(p):
        return {"nodes": [{"node_id": "1"}, {"node_id": "2"}]}
        
    # Manually calculate what the hash would be
    # nodes = 1, 2 -> ids = "12" -> md5("12")
    expected_hash = hashlib.md5(b"12").hexdigest()[:8]
    
    # Set initial state hash to be the SAME as what extract will return
    # This simulates "Start State == End State"
    state_hash = expected_hash 
    
    print(f"Initial State Hash: {state_hash}")
    
    # --- Simulate the Logic Block from app.py ---
    action = 'click'
    result = await mock_execute(page, {}, {})
    
    # THE LOGIC WE ADDED:
    if result.get('ok') and action in ['click', 'type', 'submit']:
        try:
            # Re-capture
            new_dom = await mock_extract(page)
            new_node_ids = "".join(sorted([n.get('node_id', '') for n in new_dom.get('nodes', [])]))
            new_hash = hashlib.md5(new_node_ids.encode()).hexdigest()[:8]
            
            print(f"New Hash: {new_hash}")
            
            if new_hash == state_hash:
                print(f"  [{session_id}] ⚠️ NO-OP DETECTED: Action succeeded but state unchanged")
                result['message'] += " [⚠️ WARNING: Page state did not change]"
                result['no_op'] = True
        except Exception as e:
            print(f"Check error: {e}")
            
    # --- Verification ---
    print(f"Final Result Message: {result['message']}")
    
    if "WARNING" in result['message'] and result.get('no_op'):
        print("PASS: No-Op detected correctly.")
    else:
        print("FAIL: No-Op NOT detected.")

if __name__ == "__main__":
    asyncio.run(test_loop_detection())
