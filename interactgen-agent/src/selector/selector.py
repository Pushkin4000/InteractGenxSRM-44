"""
Vision-enhanced selector with multi-modal approach.
Combines DOM analysis with computer vision for robust element selection.
"""
import json
import sys
import os
import argparse
from typing import List, Dict, Any, Optional
from Levenshtein import distance as levenshtein_distance
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.selector_history import get_boost_score


def score_dom_candidate(candidate: Dict, node: Dict, target: str, match_count: int = 1) -> float:
    """
    Score a DOM-based selector candidate.
    
    Scoring rules:
    - Base: aria/id (+0.35), name (+0.25), text (+0.18), CSS ID (+0.15)
    - Modifiers: unique match (+0.3), visible (+0.12), dynamic (-0.35), history (+0.15)
    """
    score = 0.0
    
    # Base scoring by provenance
    prov = candidate.get('prov', '')
    if prov == 'aria':
        score += 0.35
    elif prov == 'id':
        score += 0.35
    elif prov == 'name':
        score += 0.25
    elif prov == 'text':
        score += 0.18
    elif prov == 'role':
        score += 0.28
    elif prov == 'class':
        score += 0.15
    
    # CSS ID selector bonus
    if candidate.get('type') == 'css' and candidate.get('value', '').startswith('#'):
        score += 0.15
    
    # Unique match bonus
    if match_count == 1:
        score += 0.3
    
    # Visible bonus
    if node.get('visible', False):
        score += 0.12
    
    # Dynamic ID penalty
    if candidate.get('dynamic', False):
        score -= 0.35
    
    # Success history boost
    history_boost = get_boost_score(node.get('node_id', ''), candidate.get('value', ''))
    score += history_boost
    
    # Cap score to [0.0, 1.0]
    return max(0.0, min(1.0, score))


def fuzzy_match(text1: str, text2: str, threshold: int = 2) -> bool:
    """Check if two strings are similar using Levenshtein distance."""
    if not text1 or not text2:
        return False
    
    text1 = text1.lower().strip()
    text2 = text2.lower().strip()
    
    # Exact match
    if text1 == text2:
        return True
    
    # Substring match
    if text1 in text2 or text2 in text1:
        return True
    
    # Levenshtein distance
    dist = levenshtein_distance(text1, text2)
    return dist <= threshold


def match_node_to_target(node: Dict, target: str) -> bool:
    """Check if a node matches the target description."""
    target_lower = target.lower()
    
    # Check semantic label
    if node.get('semantic_label') and fuzzy_match(node['semantic_label'], target):
        return True
    
    # Check aria label
    if node.get('aria_label') and fuzzy_match(node['aria_label'], target):
        return True
    
    # Check text content
    if node.get('text') and fuzzy_match(node['text'], target):
        return True
    
    # Check any attribute values
    for attr_value in node.get('attributes', {}).values():
        if isinstance(attr_value, str) and fuzzy_match(attr_value, target):
            return True
    
    # Check if target keywords appear in node
    target_words = set(target_lower.split())
    
    # Safe concatenation handling None values
    n_text = node.get('text') or ''
    n_aria = node.get('aria_label') or ''
    node_text = (n_text + ' ' + n_aria).lower()
    
    node_words = set(node_text.split())
    
    # If most target words appear in node, it's a match
    if len(target_words) > 0:
        overlap = len(target_words & node_words)
        if overlap / len(target_words) >= 0.6:  # 60% overlap
            return True
    
    return False


def select_candidates_dom(snapshot: Dict, target: str, max_candidates: int = 3) -> List[Dict]:
    """
    DOM-based selector strategy.
    Returns ranked candidates based on DOM selectors.
    """
    nodes = snapshot.get('nodes', [])
    matched_candidates = []
    
    # Find nodes that match the target description
    for node in nodes:
        if not match_node_to_target(node, target):
            continue
        
        # Score each candidate for this node
        for candidate in node.get('candidates', []):
            # Assume match_count = 1 for now (could query snapshot for actual count)
            match_count = 1
            
            score = score_dom_candidate(candidate, node, target, match_count)
            
            matched_candidates.append({
                "node_id": node['node_id'],
                "type": candidate['type'],
                "value": candidate['value'],
                "match_count": match_count,
                "score": score,
                "strategy": "dom"
            })
    
    # Sort by score descending
    matched_candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return matched_candidates[:max_candidates]


def select_candidates_vision(snapshot: Dict, target: str, visual_hint: Optional[str] = None) -> List[Dict]:
    """
    Vision-based selector strategy (fallback).
    Uses visual hints and spatial reasoning.
    
    NOTE: This is a simplified implementation. Full vision matching would use:
    - OCR with Tesseract
    - Template matching with OpenCV
    - Pattern recognition for icons
    """
    # Placeholder for vision-based selection
    # In a full implementation, this would:
    # 1. Use bounding boxes to find elements in spatial regions
    # 2. Apply OCR to element screenshots
    # 3. Use template matching for visual similarity
    # 4. Score based on visual features
    
    nodes = snapshot.get('nodes', [])
    vision_candidates = []
    
    # Simple spatial heuristics as placeholder
    if visual_hint:
        hint_lower = visual_hint.lower()
        
        for node in nodes:
            bbox = node.get('bounding_box', {})
            
            # Top-right heuristic
            if 'top' in hint_lower and 'right' in hint_lower:
                if bbox.get('y', 999) < 200 and bbox.get('x', 0) > 800:
                    vision_candidates.append({
                        "node_id": node['node_id'],
                        "type": "css",
                        "value": node.get('css_path', ''),
                        "match_count": 1,
                        "score": 0.7,
                        "strategy": "vision",
                        "visual_score": 0.8
                    })
            
            # Button heuristic
            if 'button' in hint_lower and node.get('tag') == 'button':
                vision_candidates.append({
                    "node_id": node['node_id'],
                    "type": "css",
                    "value": node.get('css_path', ''),
                    "match_count": 1,
                    "score": 0.6,
                    "strategy": "vision",
                    "visual_score": 0.7
                })
    
    vision_candidates.sort(key=lambda x: x['score'], reverse=True)
    return vision_candidates[:3]


def select_candidates_hybrid(snapshot: Dict, target: str, visual_hint: Optional[str] = None, max_candidates: int = 3) -> List[Dict]:
    """
    Hybrid selector strategy.
    Combines DOM (60%) and vision (40%) scores.
    """
    dom_cands = select_candidates_dom(snapshot, target, max_candidates * 2)
    vision_cands = select_candidates_vision(snapshot, target, visual_hint)
    
    # Merge candidates
    hybrid_cands = {}
    
    for cand in dom_cands:
        key = cand['node_id']
        hybrid_cands[key] = cand
        hybrid_cands[key]['dom_score'] = cand['score']
        hybrid_cands[key]['visual_score'] = 0.0
    
    for cand in vision_cands:
        key = cand['node_id']
        if key in hybrid_cands:
            hybrid_cands[key]['visual_score'] = cand.get('visual_score', 0.5)
        else:
            hybrid_cands[key] = cand
            hybrid_cands[key]['dom_score'] = 0.0
    
    # Compute hybrid score: 60% DOM + 40% vision
    for key in hybrid_cands:
        cand = hybrid_cands[key]
        dom_score = cand.get('dom_score', cand.get('score', 0.0))
        visual_score = cand.get('visual_score', 0.0)
        cand['score'] = 0.6 * dom_score + 0.4 * visual_score
        cand['strategy'] = 'hybrid'
    
    # Sort and return top candidates
    result = list(hybrid_cands.values())
    result.sort(key=lambda x: x['score'], reverse=True)
    
    return result[:max_candidates]


def select_candidates(snapshot_path: str, steps_path: str, output_path: str = "candidates.json", strategy: str = "hybrid"):
    """
    Main selector function.
    
    Args:
        snapshot_path: Path to snapshot JSON
        steps_path: Path to semantic steps JSON
        output_path: Path to output candidates JSON
        strategy: "dom", "vision", or "hybrid"
    """
    # Load snapshot
    with open(snapshot_path, 'r', encoding='utf-8') as f:
        snapshot = json.load(f)
    
    # Load steps
    with open(steps_path, 'r', encoding='utf-8') as f:
        steps = json.load(f)
    
    # Select candidates for each step
    all_candidates = {}
    
    for step in steps:
        step_id = step.get('step_id')
        target = step.get('target', '')
        visual_hint = step.get('visual_hint')
        
        if not target or step.get('action') == 'navigate':
            continue
        
        print(f"Selecting candidates for {step_id}: {target}")
        
        # Choose strategy
        if strategy == "dom":
            candidates = select_candidates_dom(snapshot, target)
        elif strategy == "vision":
            candidates = select_candidates_vision(snapshot, target, visual_hint)
        else:  # hybrid
            candidates = select_candidates_hybrid(snapshot, target, visual_hint)
        
        all_candidates[step_id] = {
            "target": target,
            "candidates": candidates
        }
        
        print(f"  Found {len(candidates)} candidates (strategy: {strategy})")
        if candidates:
            print(f"  Top: {candidates[0]['value']} (score: {candidates[0]['score']:.3f})")
    
    # Save to output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_candidates, f, indent=2)
    
    print(f"\nCandidates saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Select element candidates using multi-modal approach")
    parser.add_argument("snapshot", help="Path to snapshot JSON")
    parser.add_argument("steps", help="Path to steps JSON")
    parser.add_argument("--output", "-o", help="Output candidates JSON", default="candidates.json")
    parser.add_argument("--strategy", choices=["dom", "vision", "hybrid"], default="hybrid",
                        help="Selector strategy: dom (fast), vision (robust), or hybrid (best)")
    
    args = parser.parse_args()
    
    select_candidates(args.snapshot, args.steps, args.output, args.strategy)


if __name__ == "__main__":
    main()
