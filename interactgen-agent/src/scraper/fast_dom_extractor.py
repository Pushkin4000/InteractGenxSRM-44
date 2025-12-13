"""
Fast async DOM extractor using in-page JavaScript injection.
Extracts DOM structure from already-open Playwright page in ~50-100ms.
"""
import hashlib
from typing import Dict, List, Any


# JavaScript code injected into page for fast DOM extraction
DOM_EXTRACTION_JS = r'''() => {
    const nodes = [];
    const allElements = document.querySelectorAll('body *');
    
    allElements.forEach((el, idx) => {
        try {
            // Skip invisible elements
            const style = getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return;
            
            // Get bounding box
            const rect = el.getBoundingClientRect();
            if (rect.width < 10 || rect.height < 10) return;
            
            // Skip elements outside viewport (with margin)
            if (rect.bottom < -100 || rect.top > window.innerHeight + 100) return;
            
            // Get text content (limited to 100 chars for speed)
            let text = '';
            if (el.tagName !== 'SCRIPT' && el.tagName !== 'STYLE') {
                text = el.innerText?.trim().slice(0, 100) || '';
            }
            
            // Generate simple XPath
            let xpath = '';
            let current = el;
            while (current && current.nodeType === 1) {
                let part = current.tagName.toLowerCase();
                if (current.id) {
                    part = `//*[@id="${current.id}"]`;
                    xpath = part + xpath;
                    break;
                }
                let sibling = current.previousElementSibling;
                let index = 1;
                while (sibling) {
                    if (sibling.tagName === current.tagName) index++;
                    sibling = sibling.previousElementSibling;
                }
                part = `/${part}[${index}]`;
                xpath = part + xpath;
                current = current.parentElement;
            }
            if (!xpath.startsWith('//')) xpath = '/' + xpath;
            
            // Get selector candidates
            const candidates = [];

            // 1. Data Attributes (High reliability)
            ['data-testid', 'data-test', 'data-cy', 'data-id'].forEach(attr => {
                if (el.hasAttribute(attr)) {
                    candidates.push({
                        type: 'css',
                        value: `[${attr}="${el.getAttribute(attr)}"]`,
                        prov: 'data-attr',
                        score: 0.95
                    });
                }
            });
            
            // 2. ID selector
            if (el.id && !/\d{4,}/.test(el.id)) {
                candidates.push({
                    type: 'css',
                    value: `#${el.id}`,
                    prov: 'id',
                    score: 0.9
                });
            }

            // 3. Aria-label selector
            const ariaLabel = el.getAttribute('aria-label');
            if (ariaLabel) {
                candidates.push({
                    type: 'css',
                    value: `[aria-label="${ariaLabel.replace(/"/g, '\\"')}"]`,
                    prov: 'aria',
                    score: 0.85
                });
            }
            
            // 4. Name attribute
            const name = el.getAttribute('name');
            if (name) {
                candidates.push({
                    type: 'css',
                    value: `[name="${name}"]`,
                    prov: 'name',
                    score: 0.8
                });
            }
            
            // 5. Role attribute
            const role = el.getAttribute('role');
            if (role) {
                candidates.push({
                    type: 'css',
                    value: `[role="${role}"]`,
                    prov: 'role',
                    score: 0.7
                });
            }

            // 6. Placeholder
            const ph = el.getAttribute('placeholder');
            if (ph) {
                 candidates.push({
                    type: 'css',
                    value: `[placeholder="${ph.replace(/"/g, '\\"')}"]`,
                    prov: 'placeholder',
                    score: 0.75
                });
            }
            
            // 7. Text-based XPath (for buttons/links)
            if (text && text.length < 50 && ['BUTTON', 'A', 'LABEL', 'SPAN', 'DIV'].includes(el.tagName)) {
                candidates.push({
                    type: 'xpath',
                    value: `//${el.tagName.toLowerCase()}[normalize-space(text())="${text.replace(/"/g, '\\"')}"]`,
                    prov: 'text',
                    score: 0.6
                });
            }
            
            nodes.push({
                node_id: `n_${idx}`,
                tag: el.tagName.toLowerCase(),
                text: text,
                aria_label: ariaLabel || null,
                attributes: {
                    id: el.id || null,
                    class: el.className || null,
                    name: name || null,
                    role: role || null,
                    type: el.getAttribute('type') || null,
                    placeholder: el.getAttribute('placeholder') || null,
                    href: el.getAttribute('href') || null,
                    'data-testid': el.getAttribute('data-testid') || null
                },
                xpath: xpath,
                bounding_box: {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height)
                },
                visible: true,
                candidates: candidates
            });
        } catch (e) {
            // Skip problematic elements
        }
    });
    
    return {
        url: location.href,
        timestamp: Date.now(),
        nodes: nodes,
        viewport: {
            width: window.innerWidth,
            height: window.innerHeight
        }
    };
}'''


async def extract_dom_fast(page) -> Dict[str, Any]:
    """
    Extract DOM structure from an already-open Playwright page.
    
    This is MUCH faster than launching a new browser:
    - ~50-100ms vs 5-15 seconds
    - Uses existing browser session
    - Gets real-time page state
    
    Args:
        page: Playwright async page object (already navigated)
    
    Returns:
        Dict with nodes, url, timestamp, viewport
    """
    try:
        # Inject and execute JavaScript
        snapshot_data = await page.evaluate(DOM_EXTRACTION_JS)
        
        # Generate stable node IDs based on content
        for node in snapshot_data.get('nodes', []):
            # Create stable ID from element properties
            tag = node.get('tag', '')
            text = node.get('text', '')[:80]
            bbox = node.get('bounding_box', {})
            s = f"{tag}|{text}|{bbox.get('x', 0)}|{bbox.get('y', 0)}"
            node['node_id'] = hashlib.sha1(s.encode()).hexdigest()[:12]
        
        return snapshot_data
    
    except Exception as e:
        return {
            'url': '',
            'timestamp': 0,
            'nodes': [],
            'error': str(e)
        }


def extract_dom_sync(page) -> Dict[str, Any]:
    """
    Synchronous version for sync Playwright pages.
    """
    try:
        snapshot_data = page.evaluate(DOM_EXTRACTION_JS)
        
        for node in snapshot_data.get('nodes', []):
            tag = node.get('tag', '')
            text = node.get('text', '')[:80]
            bbox = node.get('bounding_box', {})
            s = f"{tag}|{text}|{bbox.get('x', 0)}|{bbox.get('y', 0)}"
            node['node_id'] = hashlib.sha1(s.encode()).hexdigest()[:12]
        
        return snapshot_data
    
    except Exception as e:
        return {
            'url': '',
            'timestamp': 0,
            'nodes': [],
            'error': str(e)
        }


# JavaScript for highlighting an element before action
HIGHLIGHT_JS = '''(selector) => {
    try {
        let el = null;
        
        // Try CSS selector first
        if (!selector.startsWith('/')) {
            el = document.querySelector(selector);
        }
        
        // Try XPath
        if (!el && selector.startsWith('/')) {
            el = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        }
        
        if (el) {
            // Store original styles
            const originalOutline = el.style.outline;
            const originalBoxShadow = el.style.boxShadow;
            const originalTransition = el.style.transition;
            
            // Apply highlight
            el.style.transition = 'all 0.2s ease';
            el.style.outline = '3px solid #f59e0b';
            el.style.boxShadow = '0 0 20px rgba(245, 158, 11, 0.6)';
            
            // Scroll into view
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            return true;
        }
        return false;
    } catch (e) {
        return false;
    }
}'''

REMOVE_HIGHLIGHT_JS = '''(selector) => {
    try {
        let el = document.querySelector(selector) || 
                 document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        if (el) {
            el.style.outline = '';
            el.style.boxShadow = '';
        }
    } catch (e) {}
}'''


async def highlight_element(page, selector: str) -> bool:
    """Highlight an element on the page for user visibility."""
    try:
        return await page.evaluate(HIGHLIGHT_JS, selector)
    except:
        return False


async def remove_highlight(page, selector: str):
    """Remove highlight from an element."""
    try:
        await page.evaluate(REMOVE_HIGHLIGHT_JS, selector)
    except:
        pass
