"""
Async executor for real-time step execution.
Works with already-open Playwright async pages.
"""
import asyncio
from typing import Dict, List, Any, Optional


async def execute_step_async(page, step: Dict, dom: Dict) -> Dict:
    """
    Execute a single step on an already-open async page.
    
    Args:
        page: Playwright async page object
        step: Step dict with action, target, value, etc.
        dom: Current DOM snapshot for finding elements
    
    Returns:
        Result dict with ok, message, time_ms
    """
    import time
    start = time.time()
    
    action = step.get('action', '')
    target = step.get('target', '')
    value = step.get('value', '') or step.get('text', '')  # Support both 'value' and 'text' keys
    
    result = {
        "step_id": step.get('step_id', 'unknown'),
        "ok": False,
        "message": "",
        "time_ms": 0
    }
    
    try:
        if action == 'done':
            result['ok'] = True
            result['message'] = step.get('reason', 'Task complete')
            return result
        
        # Find best selector from DOM or use provided selector
        selector = step.get('selector') or find_best_selector(target, dom)
        
        if not selector:
            # Try one more time with a more aggressive search
            target_lower = target.lower()
            for node in dom.get('nodes', []):
                node_text = (node.get('text') or '').lower()
                node_aria = (node.get('aria_label') or '').lower()
                if target_lower in node_text or target_lower in node_aria or any(word in node_text for word in target_lower.split() if len(word) > 2):
                    candidates = node.get('candidates', [])
                    if candidates:
                        selector = candidates[0].get('value')
                        break
                    elif node.get('xpath'):
                        selector = node.get('xpath')
                        break
            
            if not selector:
                result['message'] = f"Could not find selector for: {target}"
                return result
        
        if action == 'click':
            try:
                await page.click(selector, timeout=3000)
                result['ok'] = True
                result['message'] = f"Clicked: {target}"
            except Exception as e:
                # Fallback to JS click
                try:
                    await page.evaluate(f'''(sel) => {{
                        const el = document.querySelector(sel) || 
                                   document.evaluate(sel, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                        if (el) el.click();
                    }}''', selector)
                    result['ok'] = True
                    result['message'] = f"Clicked (JS): {target}"
                except Exception as e2:
                    result['message'] = f"Click failed: {e2}"
        
        elif action == 'type':
            if not value:
                result['message'] = f"No value provided for typing into: {target}"
                return result
            
            try:
                # First, try to focus and clear the field, then type
                try:
                    # Try to find and focus the element
                    element = await page.query_selector(selector)
                    if element:
                        await element.focus()
                        await asyncio.sleep(0.1)  # Brief pause for focus
                        # Clear existing value
                        await element.fill('')
                        await asyncio.sleep(0.1)
                        # Type the new value
                        await element.fill(value)
                        result['ok'] = True
                        result['message'] = f"Typed '{value}' into: {target}"
                    else:
                        raise Exception("Element not found")
                except:
                    # Fallback: use page.fill directly
                    await page.fill(selector, value, timeout=3000)
                    result['ok'] = True
                    result['message'] = f"Typed '{value}' into: {target}"
            except Exception as e:
                # Fallback to JS with proper escaping
                try:
                    # Properly escape the value for JavaScript
                    escaped = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')
                    
                    js_code = f'''([sel, val]) => {{
                        let el = null;
                        // Try CSS selector first
                        if (!sel.startsWith('/')) {{
                            el = document.querySelector(sel);
                        }}
                        // Try XPath
                        if (!el && sel.startsWith('/')) {{
                            el = document.evaluate(sel, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                        }}
                        if (el) {{
                            // Focus the element
                            el.focus();
                            // Clear existing value
                            el.value = '';
                            // Set new value
                            el.value = val;
                            // Trigger events to ensure form validation works
                            el.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true, cancelable: true }}));
                            el.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true }}));
                            return true;
                        }}
                        return false;
                    }}'''
                    
                    success = await page.evaluate(js_code, [selector, value])
                    if success:
                        result['ok'] = True
                        result['message'] = f"Typed (JS) '{value}' into: {target}"
                    else:
                        result['message'] = f"Type failed: Element not found with selector: {selector}"
                except Exception as e2:
                    result['message'] = f"Type failed: {str(e2)}"
            
            # Auto-press Enter for search fields if successful
            if result['ok'] and ('search' in target.lower() or 'query' in target.lower()):
                try:
                    await page.keyboard.press('Enter')
                    result['message'] += " + Pressed Enter"
                except:
                    pass
        
        elif action == 'scroll':
            direction = value.lower() if value else 'down'
            amount = 500 if direction == 'down' else -500
            await page.evaluate(f"window.scrollBy(0, {amount})")
            result['ok'] = True
            result['message'] = f"Scrolled {direction}"
        
        elif action == 'wait':
            await asyncio.sleep(1)
            result['ok'] = True
            result['message'] = "Waited 1 second"
        
        elif action == 'navigate':
            await page.goto(target, timeout=15000)
            result['ok'] = True
            result['message'] = f"Navigated to: {target}"
        
        else:
            result['message'] = f"Unknown action: {action}"
    
    except Exception as e:
        result['message'] = f"Error: {str(e)}"
    
    result['time_ms'] = int((time.time() - start) * 1000)
    return result


def find_best_selector(target: str, dom: Dict) -> Optional[str]:
    """
    Find the best CSS/XPath selector for a semantic target description.
    
    Searches DOM nodes for matches based on:
    - Text content
    - aria-label
    - name attribute
    - placeholder
    """
    target_lower = target.lower()
    target_words = set(target_lower.split())
    
    best_match = None
    best_score = 0
    
    for node in dom.get('nodes', []):
        score = 0
        
        # Check text content
        text = (node.get('text') or '').lower()
        if target_lower in text or text in target_lower:
            score += 0.5
        
        # Check aria-label
        aria = (node.get('aria_label') or '').lower()
        if target_lower in aria or aria in target_lower:
            score += 0.6
        
        # Check attributes
        attrs = node.get('attributes', {})
        
        name = (attrs.get('name') or '').lower()
        if target_lower in name or name in target_lower:
            score += 0.5
        
        placeholder = (attrs.get('placeholder') or '').lower()
        if target_lower in placeholder or placeholder in target_lower:
            score += 0.4
        
        # Keyword overlap
        node_text = f"{text} {aria} {name} {placeholder}".lower()
        node_words = set(node_text.split())
        overlap = len(target_words & node_words)
        if target_words:
            score += 0.3 * (overlap / len(target_words))
        
        # Tag matching
        tag = node.get('tag', '')
        if 'button' in target_lower and tag == 'button':
            score += 0.2
        if 'input' in target_lower and tag == 'input':
            score += 0.2
        if 'link' in target_lower and tag == 'a':
            score += 0.2
        
        if score > best_score:
            best_score = score
            best_match = node
    
    if not best_match or best_score < 0.2:
        return None
    
    # Get selector from candidates
    candidates = best_match.get('candidates', [])
    if candidates:
        # Prefer high-score candidates
        candidates.sort(key=lambda c: c.get('score', 0), reverse=True)
        return candidates[0].get('value')
    
    # Fallback to xpath
    return best_match.get('xpath')
