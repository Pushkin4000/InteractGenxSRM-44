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
        
        # Find all potential candidates to retry
        candidates_to_try = []
        
        # 1. Try Find by Element ID (High Precision)
        element_id = step.get('element_id')
        if element_id:
            for node in dom.get('nodes', []):
                if node.get('node_id') == element_id:
                    # Add all candidates from this node
                    node_candidates = node.get('candidates', [])
                    if node_candidates:
                        # Sort by score
                        node_candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
                        for c in node_candidates:
                            candidates_to_try.append(c.get('value'))
                    
                    # Add XPath as backup
                    if node.get('xpath'):
                        candidates_to_try.append(node.get('xpath'))
                        
                    if candidates_to_try:
                        result['message'] += f" [Resolved ID: {element_id}]"
                    break
        
        # 2. Add best fuzzy match selector if provided
        selector = step.get('selector')
        if selector and selector not in candidates_to_try:
            candidates_to_try.insert(0, selector)
            
        # 3. Fallback to fuzzy search if no ID matches or candidates found
        if not candidates_to_try:
            best_selector = find_best_selector(target, dom)
            if best_selector:
                candidates_to_try.append(best_selector)
            
            # 4. Try one more time with a more aggressive search
            if not candidates_to_try:
                target_lower = target.lower()
                for node in dom.get('nodes', []):
                    node_text = (node.get('text') or '').lower()
                    node_aria = (node.get('aria_label') or '').lower()
                    node_id = node.get('node_id', '')
                    
                    if (target_lower in node_text or 
                        target_lower in node_aria or 
                        (node_id and node_id in target_lower) or
                        any(word in node_text for word in target_lower.split() if len(word) > 2)):
                        
                        node_candidates = node.get('candidates', [])
                        if node_candidates:
                            candidates_to_try.append(node_candidates[0].get('value'))
                            break
                        elif node.get('xpath'):
                            candidates_to_try.append(node.get('xpath'))
                            break

        if not candidates_to_try:
            result['message'] = f"Could not find selector for: {target} (ID: {element_id})"
            return result
            
        # Deduplicate while preserving order
        candidates_to_try = list(dict.fromkeys(candidates_to_try))
        # Limit to top 3 candidates to avoid taking too long
        candidates_to_try = candidates_to_try[:3] 
        
        # Attempt execution with retries
        success = False
        last_error = ""
        
        for idx, selector in enumerate(candidates_to_try):
            try:
                if action == 'click':
                    try:
                        # Try standard click first
                        await page.click(selector, timeout=2000)
                        result['ok'] = True
                        result['message'] = f"Clicked: {target}"
                        success = True
                        break
                    except Exception as e:
                        # Fallback to JS click immediately for this selector
                        try:
                            await page.evaluate(f'''(sel) => {{
                                const el = document.querySelector(sel) || 
                                           document.evaluate(sel, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                if (el) {{
                                    el.click();
                                    return true;
                                }}
                                return false;
                            }}''', selector)
                            result['ok'] = True
                            result['message'] = f"Clicked (JS): {target}"
                            success = True
                            break
                        except Exception as e2:
                            last_error = f"Click failed with {selector}: {str(e2)}"
                            # Continue to next candidate
                
                elif action == 'type':
                    if not value:
                        result['message'] = f"No value provided for typing into: {target}"
                        return result
                    
                    try:
                        # Try efficient fill first
                        await page.fill(selector, value, timeout=2000)
                        result['ok'] = True
                        result['message'] = f"Typed '{value}' into: {target}"
                        success = True
                        
                        # Auto-press Enter for search fields
                        if 'search' in target.lower() or 'query' in target.lower():
                            try:
                                await page.keyboard.press('Enter')
                                result['message'] += " + Pressed Enter"
                            except:
                                pass
                        break
                    except Exception as e:
                        # Fallback to JS type
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
                                el.focus();
                                el.value = '';
                                el.value = val;
                                el.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
                                el.dispatchEvent(new Event('change', {{ bubbles: true, cancelable: true }}));
                                return true;
                            }}
                            return false;
                        }}'''
                        
                        if await page.evaluate(js_code, [selector, value]):
                            result['ok'] = True
                            result['message'] = f"Typed (JS) '{value}' into: {target}"
                            success = True
                            break
                        else:
                            last_error = f"JS Type failed with {selector}"
    
                elif action == 'scroll':
                    direction = value.lower() if value else 'down'
                    amount = 500 if direction == 'down' else -500
                    await page.evaluate(f"window.scrollBy(0, {amount})")
                    result['ok'] = True
                    result['message'] = f"Scrolled {direction}"
                    success = True
                    break
                    
                elif action == 'navigate':
                    await page.goto(target, timeout=15000)
                    result['ok'] = True
                    result['message'] = f"Navigated to: {target}"
                    success = True
                    break
                    
                elif action == 'wait':
                    await asyncio.sleep(1)
                    result['ok'] = True
                    result['message'] = "Waited 1 second"
                    success = True
                    break
                
                else:
                     result['message'] = f"Unknown action: {action}"
                     break
                    
            except Exception as e:
                last_error = str(e)
                continue
                
        if not success and not result['ok']:
            result['message'] = f"Failed to execute action after trying {len(candidates_to_try)} selectors. Last error: {last_error}"
    
    except Exception as e:
        result['message'] = f"Error: {str(e)}"
    
    result['time_ms'] = int((time.time() - start) * 1000)
    return result


def find_best_selector(target: str, dom: Dict) -> Optional[str]:
    """
    Find the best CSS/XPath selector for a semantic target description.
    Uses the robust scoring logic from selector.py.
    """
    if not target:
        return None
        
    # Import scoring logic locally to avoid circular imports during module load
    try:
        from src.selector.selector import score_dom_candidate, match_node_to_target
    except ImportError:
        # Fallback if imports fail (e.g. strict environment)
        return _find_best_selector_fallback(target, dom)
    
    nodes = dom.get('nodes', [])
    matched_candidates = []
    
    # Find nodes that match the target description
    for node in nodes:
        if not match_node_to_target(node, target):
            continue
        
        # Score each candidate for this node
        candidates = node.get('candidates', [])
        
        # If no candidates but we have xpath, create a dummy candidate
        if not candidates and node.get('xpath'):
            candidates = [{
                "type": "xpath",
                "value": node.get('xpath'),
                "prov": "xpath",
                "score": 0.5
            }]
            
        for candidate in candidates:
            # Calculate score using the robust function
            score = score_dom_candidate(candidate, node, target, match_count=1)
            
            matched_candidates.append({
                "node_id": node.get('node_id'),
                "type": candidate.get('type', 'css'),
                "value": candidate.get('value'),
                "score": score
            })
    
    # Sort by score descending
    matched_candidates.sort(key=lambda x: x['score'], reverse=True)
    
    if matched_candidates:
        best = matched_candidates[0]
        # Only return if score is reasonable
        if best['score'] > 0.3:
            return best['value']
            
    return None


def _find_best_selector_fallback(target: str, dom: Dict) -> Optional[str]:
    """Fallback implementation if imports fail."""
    target_lower = target.lower()
    target_words = set(target_lower.split())
    
    best_match = None
    best_score = 0
    
    for node in dom.get('nodes', []):
        score = 0
        
        text = (node.get('text') or '').lower()
        if target_lower in text or text in target_lower:
            score += 0.5
        
        aria = (node.get('aria_label') or '').lower()
        if target_lower in aria or aria in target_lower:
            score += 0.6
            
        attrs = node.get('attributes', {})
        name = (attrs.get('name') or '').lower()
        if target_lower in name:
            score += 0.5
            
        node_text = f"{text} {aria} {name}".lower()
        node_words = set(node_text.split())
        if target_words:
            overlap = len(target_words & node_words)
            score += 0.3 * (overlap / len(target_words))
            
        if score > best_score:
            best_score = score
            best_match = node
            
        if best_match and best_score > 0.2:
            candidates = best_match.get('candidates', [])
            if candidates:
                candidates.sort(key=lambda c: c.get('score', 0), reverse=True)
                return candidates[0].get('value')
            return best_match.get('xpath')
    
    return None
