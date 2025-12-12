"""
Fast Playwright-based DOM snapshot generator.
Captures visible interactive elements and generates ranked selector candidates.
"""
import hashlib
import json
import re
import time
import sys
from typing import Dict, List, Any
from playwright.sync_api import sync_playwright, Page, ElementHandle


def node_id(tag: str, text: str, xpath: str, bbox: Dict) -> str:
    """Generate stable node ID from element properties."""
    s = f"{tag}|{text[:80]}|{xpath}|{bbox.get('x', 0)}|{bbox.get('y', 0)}"
    return hashlib.sha1(s.encode()).hexdigest()


def looks_dynamic(s: str) -> bool:
    """Check if string looks like a dynamic ID (has long numbers or UUIDs)."""
    if not s:
        return False
    return bool(re.search(r'\d{3,}|[0-9a-f]{8}-[0-9a-f]{4}', s.lower()))


def generate_candidates(el: ElementHandle, page: Page) -> List[Dict[str, Any]]:
    """Generate ranked selector candidates for an element."""
    cands = []
    
    try:
        # Strategy 1: ARIA label or name (highest priority)
        aria = el.get_attribute("aria-label") or el.get_attribute("name")
        if aria and len(aria.strip()) > 0:
            if el.get_attribute("aria-label"):
                cands.append({
                    "type": "css",
                    "value": f"[aria-label='{aria}']",
                    "prov": "aria",
                    "score": 0.9,
                    "dynamic": False
                })
            else:
                cands.append({
                    "type": "css",
                    "value": f"[name='{aria}']",
                    "prov": "name",
                    "score": 0.85,
                    "dynamic": False
                })
        
        # Strategy 2: ID attribute
        _id = el.get_attribute("id")
        if _id and len(_id.strip()) > 0:
            is_dynamic = looks_dynamic(_id)
            cands.append({
                "type": "css",
                "value": f"#{_id}",
                "prov": "id",
                "score": 0.85 if not is_dynamic else 0.5,
                "dynamic": is_dynamic
            })
        
        # Strategy 3: Classes (limit to first 3 classes)
        cls = el.get_attribute("class") or ""
        if cls.strip():
            tag_name = el.evaluate('e => e.tagName').lower()
            cls_parts = cls.strip().split()[:3]
            cls_short = ".".join(cls_parts)
            cands.append({
                "type": "css",
                "value": f"{tag_name}.{cls_short}",
                "prov": "class",
                "score": 0.6,
                "dynamic": False
            })
        
        # Strategy 4: Text content (for buttons, links, etc.)
        text = (el.inner_text() or "").strip()
        if text and len(text) < 120:
            tag_name = el.evaluate('e => e.tagName').lower()
            # Escape single quotes in text
            text_escaped = text.replace("'", "\\'")
            cands.append({
                "type": "xpath",
                "value": f"//{tag_name}[normalize-space(text())='{text_escaped}']",
                "prov": "text",
                "score": 0.5,
                "dynamic": False
            })
        
        # Strategy 5: Role attribute (accessibility)
        role = el.get_attribute("role")
        if role:
            cands.append({
                "type": "css",
                "value": f"[role='{role}']",
                "prov": "role",
                "score": 0.7,
                "dynamic": False
            })
    
    except Exception as e:
        # If any candidate generation fails, continue with others
        pass
    
    return cands


def snapshot(url: str, out_path: str, wait_sec: float = 0.8):
    """
    Create DOM snapshot of a webpage.
    
    Args:
        url: URL to scrape
        out_path: Output path for snapshot JSON
        wait_sec: Wait time after networkidle for dynamic content
    """
    print(f"Creating snapshot of {url}...")
    
    with sync_playwright() as p:
        # Launch browser in visible mode (not headless)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            # Navigate and wait for network idle
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Additional wait for dynamic content
            time.sleep(wait_sec)
            
            # Get all elements
            els = page.query_selector_all("body *")
            nodes = []
            
            print(f"Processing {len(els)} elements...")
            
            for el in els:
                try:
                    # Skip if not visible
                    if not el.is_visible():
                        continue
                    
                    # Get bounding box
                    box = el.bounding_box()
                    if not box:
                        continue
                    
                    # Skip tiny elements (< 100px²)
                    area = box.get('width', 0) * box.get('height', 0)
                    if area < 100:
                        continue
                    
                    # Get element properties
                    tag_name = el.evaluate("e => e.tagName").lower()
                    text = (el.inner_text() or "").strip()
                    
                    # Generate XPath
                    xpath = page.evaluate("""(e) => {
                        let p = e;
                        let path = '';
                        while (p && p.nodeType === 1) {
                            let i = 1;
                            let s = p.previousElementSibling;
                            while (s) {
                                if (s.tagName === p.tagName) i++;
                                s = s.previousElementSibling;
                            }
                            path = '/' + p.tagName.toLowerCase() + '[' + i + ']' + path;
                            p = p.parentElement;
                        }
                        return path;
                    }""", el)
                    
                    # Generate CSS path
                    css_path = page.evaluate("""(e) => {
                        let parts = [];
                        let cur = e;
                        while (cur && cur.nodeType === 1) {
                            let part = cur.tagName.toLowerCase();
                            if (cur.id) {
                                part += '#' + cur.id;
                                parts.unshift(part);
                                break;
                            }
                            if (cur.className) {
                                let classes = String(cur.className).split(/\\s+/).slice(0, 3).join('.');
                                if (classes) part += '.' + classes;
                            }
                            parts.unshift(part);
                            cur = cur.parentElement;
                        }
                        return parts.join(' > ');
                    }""", el)
                    
                    # Get attributes
                    attributes = page.evaluate("""(e) => {
                        const a = {};
                        for (const attr of e.attributes) {
                            a[attr.name] = attr.value;
                        }
                        return a;
                    }""", el)
                    
                    # Generate node ID
                    nid = node_id(tag_name, text, xpath, box)
                    
                    # Generate selector candidates
                    cands = generate_candidates(el, page)
                    
                    # Create node object
                    node = {
                        "node_id": nid,
                        "tag": tag_name,
                        "text": text[:500],  # Limit text length
                        "attributes": attributes,
                        "aria_label": el.get_attribute("aria-label"),
                        "xpath": xpath,
                        "css_path": css_path,
                        "bounding_box": {
                            "x": box['x'],
                            "y": box['y'],
                            "w": box['width'],
                            "h": box['height']
                        },
                        "visible": True,
                        "semantic_label": None,
                        "candidates": cands,
                        "parent_id": None
                    }
                    
                    nodes.append(node)
                
                except Exception as e:
                    # Skip problematic elements
                    continue
            
            print(f"Captured {len(nodes)} visible elements with candidates")
            
            # Get accessibility tree (optional)
            ax_tree = None
            try:
                ax_tree = page.accessibility.snapshot()
            except:
                pass
            
            # Create snapshot object
            snapshot_obj = {
                "url": url,
                "timestamp": time.time(),
                "nodes": nodes,
                "ax_tree": ax_tree
            }
            
            # Write to file
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot_obj, f, indent=2)
            
            print(f"Snapshot saved to {out_path}")
            print(f"File size: {len(json.dumps(snapshot_obj)) / 1024:.1f} KB")
            
        finally:
            browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fast_snapshot.py <url> <output.json>")
        sys.exit(1)
    
    url = sys.argv[1]
    output = sys.argv[2]
    
    snapshot(url, output)
