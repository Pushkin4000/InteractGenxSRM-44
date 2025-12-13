"""
LLM-powered planner using Groq API (gpt-oss-120B).
Converts natural language queries to semantic automation steps.
"""
import json
import sys
import os
import argparse
from typing import List, Dict, Any
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Few-shot examples for prompt
FEW_SHOT_EXAMPLES = """
Example 1:
Query: "Add the cheapest iPhone to cart"
URL: https://amazon.com
Steps: [
  {"step_id": "s1", "action": "type", "target": "search input field", "value": "iPhone", "visual_hint": "search box at top"},
  {"step_id": "s2", "action": "click", "target": "search button", "visual_hint": "magnifying glass icon"},
  {"step_id": "s3", "action": "click", "target": "sort by price low to high", "visual_hint": "dropdown or filter option"},
  {"step_id": "s4", "action": "click", "target": "first product add to cart button", "visual_hint": "button near first product"},
  {"step_id": "s5", "action": "wait", "expect": {"type": "text_contains", "text_contains": "Added to Cart"}}
]

Example 2:
Query: "Fill contact form with name John Doe and email john@example.com"
URL: https://example.com/contact
Steps: [
  {"step_id": "s1", "action": "type", "target": "name input field", "value": "John Doe", "visual_hint": "field labeled Name or Full Name"},
  {"step_id": "s2", "action": "type", "target": "email input field", "value": "john@example.com", "visual_hint": "field labeled Email"},
  {"step_id": "s3", "action": "click", "target": "submit button", "visual_hint": "Submit or Send button at bottom"},
  {"step_id": "s4", "action": "wait", "expect": {"type": "text_contains", "text_contains": "Thank you"}}
]

Example 3:
Query: "Search for 'machine learning' and open first result"
URL: https://google.com
Steps: [
  {"step_id": "s1", "action": "type", "target": "search box", "value": "machine learning", "visual_hint": "main search input"},
  {"step_id": "s2", "action": "click", "target": "search button or press enter", "visual_hint": "Google Search button"},
  {"step_id": "s3", "action": "click", "target": "first search result link", "visual_hint": "first blue link in results"},
  {"step_id": "s4", "action": "wait", "expect": {"type": "url_contains", "value": "http"}}
]
"""


SYSTEM_PROMPT = f"""You are an expert web automation planner. Convert natural language queries into structured automation steps.

Available actions:
- navigate: Go to a URL
- click: Click an element
- type: Type text into an input field
- scroll: Scroll page (up/down)
- extract: Extract text from element
- wait: Wait for condition

Validators (for "expect" field):
- presence: Element exists
- value_equals: Input has specific value
- url_contains: URL contains substring
- text_contains: Page contains text

IMPORTANT RULES:
1. Generate semantic descriptions for "target" field (e.g., "search button", "login form email field")
2. Add "visual_hint" for each step to help visual selector (e.g., "blue button at top-right", "field labeled Email")
3. Keep steps simple and atomic
4. Use realistic step IDs (s1, s2, s3...)
5. Add validation steps when needed
6. Output ONLY valid JSON array of steps, no explanations

{FEW_SHOT_EXAMPLES}

Now convert the user's query into steps following this exact format.
"""


def plan_with_groq(query: str, url: str, snapshot_context: Dict = None, api_key: str = None) -> List[Dict[str, Any]]:
    """
    Use Groq to convert natural language query to semantic steps.
    
    Args:
        query: User's natural language query
        url: Target website URL
        snapshot_context: Optional snapshot data for context
        api_key: Groq API key (or from GROQ_API_KEY env var)
    
    Returns:
        List of semantic step dictionaries
    """
    if api_key is None:
        api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Get your free key at https://console.groq.com")
    
    client = Groq(api_key=api_key)
    
    # Build user message
    user_message = f"Query: {query}\nURL: {url}\n"
    
    # Add context from snapshot if available
    if snapshot_context and 'nodes' in snapshot_context:
        # Extract key information from snapshot
        interactive_elements = []
        for node in snapshot_context['nodes'][:20]:  # Limit to first 20 elements
            if node.get('tag') in ['button', 'a', 'input', 'select', 'textarea']:
                elem_desc = f"{node.get('tag')}"
                if node.get('text'):
                    elem_desc += f": {node.get('text')[:50]}"
                if node.get('aria_label'):
                    elem_desc += f" (aria: {node.get('aria_label')[:30]})"
                interactive_elements.append(elem_desc)
        
        if interactive_elements:
            user_message += f"\nAvailable elements on page:\n" + "\n".join(interactive_elements[:10])
    
    user_message += "\n\nGenerate steps:"
    
    # Call Groq API
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Fast and capable model
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,  # Lower temperature for more consistent output
            max_tokens=2000
        )
        
        # Extract response
        content = response.choices[0].message.content.strip()
        
        # Try to parse JSON from response
        # Sometimes LLMs wrap JSON in markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        steps = json.loads(content)
        
        # Validate structure
        if not isinstance(steps, list):
            raise ValueError("Expected list of steps")
        
        for step in steps:
            if 'step_id' not in step or 'action' not in step:
                raise ValueError(f"Step missing required fields: {step}")
        
        return steps
    
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from LLM response: {content}")
        raise ValueError(f"LLM returned invalid JSON: {e}")
    except Exception as e:
        raise ValueError(f"Error calling Groq API: {e}")


# Compact single-step planning prompt
SINGLE_STEP_SYSTEM_PROMPT = """Web automation planner. Return NEXT action as JSON only.

Actions: click, type, scroll, wait, done
Format: {"action": "click", "element_id": "12af3", "target": "search button", "value": ""}
For typing: {"action": "type", "element_id": "b4d21", "target": "email input field", "value": "user@example.com"}
If done: {"action": "done", "reason": "..."}

Rules:
- ONE step per response
- PREFER using 'element_id' from the list over fuzzy description
- Use element descriptions from provided list
- for 'type' action, extract the value to type from the goal
- Return ONLY JSON, no text"""


def plan_next_step(query: str, url: str, current_dom: Dict, 
                   executed_steps: List[Dict] = None, api_key: str = None) -> Dict[str, Any]:
    """
    Plan ONLY the next single step based on current DOM state.
    
    This enables real-time iterative execution:
    1. Scrape current DOM
    2. Plan next step
    3. Execute step
    4. Repeat until done
    
    Args:
        query: User's natural language goal
        url: Current page URL
        current_dom: Current DOM snapshot with nodes
        executed_steps: List of previously executed steps for context
        api_key: Groq API key
    
    Returns:
        Single step dict or {"action": "done"} when complete
    """
    if api_key is None:
        api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")
    
    client = Groq(api_key=api_key)
    
    # Build context about current page
    elements_summary = []
    
    # Sort nodes by score/relevance if possible, or just scan all
    # For now, we scan all nodes but limit the output list size
    
    # Filter for interactive or meaningful elements
    candidates_list = []
    interactive_tags = {'button', 'a', 'input', 'select', 'textarea', 'form', 'label', 'div', 'span'}
    
    for node in current_dom.get('nodes', []):
        tag = node.get('tag', '')
        if tag in ['script', 'style', 'meta', 'link', 'noscript', 'img', 'svg', 'path']:
            continue
            
        text = (node.get('text') or '').strip()
        aria = (node.get('aria_label') or '').strip()
        attrs = node.get('attributes', {})
        node_id = node.get('node_id', 'unknown')
        
        # Skip empty non-interactive elements
        # Allow divs/spans only if they have text or handler behavior
        if tag not in ['button', 'a', 'input', 'select', 'textarea'] and not text and not aria and not attrs.get('role'):
            continue
            
        # Build description
        parts = [f"[ID:{node_id}]", tag]
        
        if aria:
            parts.append(f"aria:{aria[:40]}")
        elif text:
            parts.append(f"'{text[:40]}'")
            
        # Add extra attributes for better identification if ID/Text is weak
        if attrs.get('name'):
            parts.append(f"name:{attrs['name'][:30]}")
        if attrs.get('placeholder'):
            parts.append(f"ph:{attrs['placeholder'][:30]}")
        if attrs.get('type'):
            parts.append(f"type:{attrs['type']}")
        if attrs.get('role'):
            parts.append(f"role:{attrs['role']}")
        if attrs.get('href') and tag == 'a':
            parts.append(f"href:{attrs['href'][:40]}")
        
        desc = " ".join(parts)
        candidates_list.append(desc)
    
    # Use up to 60 elements to give LLM enough context
    context_limit = 60
    elements_str = "\n".join(candidates_list[:context_limit])
    
    # Build compact history context
    history = ""
    if executed_steps:
        history = "\nHistory:\n"
        recent = executed_steps[-5:]  # Last 5 steps
        for s in recent:
            action = s.get('step', {}).get('action', '?')
            target = s.get('step', {}).get('target', '')[:20]
            result_status = "OK" if s.get('result', {}).get('ok') else "FAIL"
            reason = s.get('result', {}).get('message', '')
            
            # Show more context, especially for warnings
            if "WARNING" in reason or result_status == "FAIL":
                 history += f"- {action} '{target}' -> {result_status}: {reason[:100]}\n"
            else:
                 history += f"- {action} '{target}' -> {result_status}: {reason[:60]}\n"
    
    user_message = f"Goal:{query}\nURL:{url}\nEls:\n{elements_str}{history}\nNext (JSON, include 'value' if typing):"

    try:
        response = client.chat.completions.create(
            # User requested high quality model (gpt-oss-120b equiv -> llama-3.3-70b)
            model="llama-3.3-70b-versatile",  # Fast model

            messages=[
                {"role": "system", "content": SINGLE_STEP_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,  # Lower for faster, more deterministic responses
            max_tokens=200,  # Reduced from 500 - single step doesn't need much
            stream=False  # Explicitly disable streaming for faster response
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        step = json.loads(content)
        
        # Add step_id
        step_num = len(executed_steps or []) + 1
        step['step_id'] = f"s{step_num}"
        
        return step
    
    except json.JSONDecodeError as e:
        print(f"Failed to parse single step JSON: {content}")
        # Don't return "done" on parse error - return a safe action instead
        return {"action": "wait", "target": "", "value": "", "reason": f"Parse error: {str(e)[:30]}"}
    except Exception as e:
        error_str = str(e).lower()
        print(f"Error in single step planning: {e}")
        
        # Check for rate limit errors
        if 'rate limit' in error_str or '429' in error_str or 'quota' in error_str:
            raise ValueError(f"API rate limit exceeded: {e}")  # Re-raise to be handled upstream
        
        # Don't return "done" on error - return a safe action instead
        return {"action": "wait", "target": "", "value": "", "reason": f"Error: {str(e)[:30]}"}


def main():
    parser = argparse.ArgumentParser(description="Convert natural language to automation steps")
    parser.add_argument("--query", required=True, help="Natural language query")
    parser.add_argument("--url", required=True, help="Target website URL")
    parser.add_argument("--snapshot", help="Path to snapshot JSON for context", default=None)
    parser.add_argument("--output", "-o", help="Output JSON file", default="steps.json")
    
    args = parser.parse_args()
    
    # Load snapshot if provided
    snapshot_context = None
    if args.snapshot and os.path.exists(args.snapshot):
        with open(args.snapshot, 'r', encoding='utf-8') as f:
            snapshot_context = json.load(f)
    
    # Generate steps
    print(f"Planning steps for: {args.query}")
    print(f"Target URL: {args.url}")
    
    steps = plan_with_groq(args.query, args.url, snapshot_context)
    
    # Save to file
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(steps, f, indent=2)
    
    print(f"\nGenerated {len(steps)} steps:")
    for step in steps:
        print(f"  {step['step_id']}: {step['action']} - {step.get('target', 'N/A')}")
    
    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
