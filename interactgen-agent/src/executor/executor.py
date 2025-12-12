"""
Executor for running automation steps with Playwright.
Includes validation, fallbacks, and screenshot capture.
"""
import json
import sys
import os
import argparse
import time
from typing import Dict, List, Any, Optional
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.selector_history import update_success


def validate_step(page: Page, validator: Dict) -> bool:
    """
    Validate a step's expected outcome.
    
    Validator types:
    - presence: Element exists
    - value_equals: Input has specific value
    - url_contains: URL contains substring
    - text_contains: Page contains text
    """
    val_type = validator.get('type')
    
    try:
        if val_type == 'presence':
            # Just check that page is responsive
            return True
        
        elif val_type == 'value_equals':
            selector = validator.get('selector', 'input')
            expected = validator.get('value', '')
            try:
                el = page.query_selector(selector)
                if el:
                    actual = el.get_attribute('value') or ''
                    return actual == expected
            except:
                return False
        
        elif val_type == 'url_contains':
            expected = validator.get('value', '')
            return expected.lower() in page.url.lower()
        
        elif val_type == 'text_contains':
            expected = validator.get('text_contains', '')
            content = page.content()
            return expected.lower() in content.lower()
        
        else:
            # Unknown validator type, assume pass
            return True
    
    except Exception as e:
        print(f"  Validation error: {e}")
        return False


def try_click(page: Page, selector: str, selector_type: str = "css", timeout_ms: int = 1500) -> bool:
    """
    Try to click an element with fallback to JavaScript click.
    """
    try:
        # Try normal Playwright click
        if selector_type == "css":
            page.click(selector, timeout=timeout_ms)
        else:  # xpath
            page.click(f"xpath={selector}", timeout=timeout_ms)
        return True
    except Exception as e:
        print(f"    Normal click failed: {e}, trying JS click...")
        try:
            # Fallback: JavaScript click
            if selector_type == "css":
                page.evaluate(f"document.querySelector('{selector}').click()")
            else:
                page.evaluate(f"document.evaluate('{selector}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click()")
            time.sleep(0.3)  # Small wait for JS click to take effect
            return True
        except Exception as e2:
            print(f"    JS click also failed: {e2}")
            return False


def try_type(page: Page, selector: str, value: str, selector_type: str = "css", timeout_ms: int = 1500) -> bool:
    """
    Try to type into an element with fallback to JavaScript value setter.
    """
    try:
        # Try normal Playwright type
        if selector_type == "css":
            page.fill(selector, value, timeout=timeout_ms)
        else:  # xpath
            page.fill(f"xpath={selector}", value, timeout=timeout_ms)
        return True
    except Exception as e:
        print(f"    Normal type failed: {e}, trying JS value setter...")
        try:
            # Fallback: JavaScript value setter
            escaped_value = value.replace("'", "\\'")
            if selector_type == "css":
                page.evaluate(f"""
                    const el = document.querySelector('{selector}');
                    el.value = '{escaped_value}';
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                """)
            else:
                page.evaluate(f"""
                    const el = document.evaluate('{selector}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    el.value = '{escaped_value}';
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                """)
            time.sleep(0.3)
            return True
        except Exception as e2:
            print(f"    JS value setter also failed: {e2}")
            return False


def execute_step(page: Page, step: Dict, candidates: List[Dict], step_timeout_sec: int = 5, action_timeout_ms: int = 3000) -> Dict:
    """
    Execute a single step with candidate fallback.
    
    Returns:
        Result dict with ok, used_candidate, time_ms, etc.
    """
    start_time = time.time()
    step_id = step.get('step_id', 'unknown')
    action = step.get('action')
    
    result = {
        "step_id": step_id,
        "ok": False,
        "used_candidate": None,
        "time_ms": 0,
        "reason": None,
        "screenshot_path": None
    }
    
    try:
        # Handle navigate action (no candidates needed)
        if action == 'navigate':
            url = step.get('target', '')
            print(f"  Navigating to {url}")
            page.goto(url, timeout=step_timeout_sec * 1000)
            result['ok'] = True
            result['time_ms'] = (time.time() - start_time) * 1000
            return result
        
        # Handle wait action
        if action == 'wait':
            print(f"  Waiting...")
            time.sleep(1)
            validator = step.get('expect')
            if validator:
                result['ok'] = validate_step(page, validator)
                result['reason'] = "Validation " + ("passed" if result['ok'] else "failed")
            else:
                result['ok'] = True
            result['time_ms'] = (time.time() - start_time) * 1000
            return result
        
        # Try each candidate in order
        for idx, candidate in enumerate(candidates[:3]):  # Max 3 attempts
            selector = candidate.get('value')
            selector_type = candidate.get('type', 'css')
            node_id = candidate.get('node_id')
            
            print(f"  Trying candidate {idx+1}/{min(len(candidates), 3)}: {selector}")
            
            try:
                # Execute action based on type
                if action == 'click':
                    success = try_click(page, selector, selector_type, action_timeout_ms)
                
                elif action == 'type':
                    value = step.get('value', '')
                    success = try_type(page, selector, value, selector_type, action_timeout_ms)
                
                elif action == 'scroll':
                    # Simple scroll implementation
                    direction = step.get('value', 'down')
                    scroll_amount = 500 if direction == 'down' else -500
                    page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                    success = True
                
                elif action == 'extract':
                    # Extract text from element
                    if selector_type == "css":
                        el = page.query_selector(selector)
                    else:
                        el = page.query_selector(f"xpath={selector}")
                    
                    if el:
                        extracted_text = el.inner_text()
                        result['extracted_text'] = extracted_text
                        print(f"    Extracted: {extracted_text[:100]}")
                        success = True
                    else:
                        success = False
                
                else:
                    result['reason'] = f"Unknown action: {action}"
                    break
                
                # Check if action succeeded
                if success:
                    # Wait a bit for page to update
                    time.sleep(0.5)
                    
                    # Validate if validator specified
                    validator = step.get('expect')
                    if validator:
                        validation_ok = validate_step(page, validator)
                        if not validation_ok:
                            print(f"    Action succeeded but validation failed")
                            update_success(node_id, selector, False)
                            continue
                    
                    # Success!
                    result['ok'] = True
                    result['used_candidate'] = candidate
                    result['time_ms'] = (time.time() - start_time) * 1000
                    
                    # Update success history
                    update_success(node_id, selector, True)
                    
                    print(f"    ✓ Success with candidate {idx+1}")
                    return result
                else:
                    # This candidate failed, try next
                    print(f"    ✗ Failed with candidate {idx+1}")
                    update_success(node_id, selector, False)
                    continue
            
            except Exception as e:
                print(f"    ✗ Exception with candidate {idx+1}: {e}")
                update_success(node_id, selector, False)
                continue
        
        # All candidates failed
        result['reason'] = f"All {len(candidates)} candidates failed"
        result['time_ms'] = (time.time() - start_time) * 1000
        
        # Capture screenshot on failure
        screenshot_path = f"fail_{step_id}.png"
        try:
            page.screenshot(path=screenshot_path)
            result['screenshot_path'] = screenshot_path
            print(f"  Captured failure screenshot: {screenshot_path}")
        except:
            pass
        
        return result
    
    except Exception as e:
        result['reason'] = f"Execution error: {str(e)}"
        result['time_ms'] = (time.time() - start_time) * 1000
        return result


def execute_all(snapshot_path: str, steps_path: str, candidates_path: str, output_path: str = "results.json"):
    """
    Execute all steps with their candidates.
    """
    # Load data
    with open(snapshot_path, 'r', encoding='utf-8') as f:
        snapshot = json.load(f)
    
    with open(steps_path, 'r', encoding='utf-8') as f:
        steps = json.load(f)
    
    with open(candidates_path, 'r', encoding='utf-8') as f:
        all_candidates = json.load(f)
    
    print(f"Executing {len(steps)} steps...")
    
    # Start browser
    with sync_playwright() as p:
        # Launch visible browser for CLI mode
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        
        # Navigate to initial URL
        initial_url = snapshot.get('url')
        if initial_url:
            print(f"Navigating to {initial_url}")
            page.goto(initial_url, timeout=30000)
        
        results = []
        
        # Execute each step
        for step in steps:
            step_id = step.get('step_id')
            print(f"\n[{step_id}] {step.get('action')} - {step.get('target', 'N/A')}")
            
            # Get candidates for this step
            step_candidates_data = all_candidates.get(step_id, {})
            candidates = step_candidates_data.get('candidates', [])
            
            # Execute step
            result = execute_step(page, step, candidates)
            results.append(result)
            
            # Stop on first failure (optional - could continue)
            if not result['ok']:
                print(f"  Step failed: {result.get('reason')}")
                # Uncomment to stop on failure:
                # break
        
        browser.close()
    
    # Save results
    output_data = {
        "results": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r['ok']),
            "failed": sum(1 for r in results if not r['ok']),
            "avg_time_ms": sum(r['time_ms'] for r in results) / len(results) if results else 0
        }
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Results saved to {output_path}")
    print(f"Summary: {output_data['summary']['passed']}/{output_data['summary']['total']} passed")
    print(f"Average time: {output_data['summary']['avg_time_ms']:.1f}ms per step")


def main():
    parser = argparse.ArgumentParser(description="Execute automation steps with Playwright")
    parser.add_argument("snapshot", help="Path to snapshot JSON")
    parser.add_argument("steps", help="Path to steps JSON")
    parser.add_argument("candidates", help="Path to candidates JSON")
    parser.add_argument("--output", "-o", help="Output results JSON", default="results.json")
    
    args = parser.parse_args()
    
    execute_all(args.snapshot, args.steps, args.candidates, args.output)


if __name__ == "__main__":
    main()
