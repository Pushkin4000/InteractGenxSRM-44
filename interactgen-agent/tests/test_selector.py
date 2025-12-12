"""
Unit tests for selector scoring algorithm.
"""
import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.selector.selector import score_dom_candidate, match_node_to_target, fuzzy_match


def test_fuzzy_match():
    """Test fuzzy matching function."""
    assert fuzzy_match("submit button", "Submit Button") == True
    assert fuzzy_match("login", "log in") == True
    assert fuzzy_match("search", "Search Box") == True
    assert fuzzy_match("hello", "world") == False


def test_aria_candidate_scores_high():
    """Aria/ID candidates should score higher than class-based."""
    node = {"node_id": "test1", "visible": True}
    
    aria_cand = {"type": "css", "value": "[aria-label='submit']", "prov": "aria", "dynamic": False}
    class_cand = {"type": "css", "value": "button.btn", "prov": "class", "dynamic": False}
    
    aria_score = score_dom_candidate(aria_cand, node, "submit", match_count=1)
    class_score = score_dom_candidate(class_cand, node, "submit", match_count=1)
    
    assert aria_score > class_score
    assert aria_score > 0.7  # Should be high score


def test_dynamic_id_penalty():
    """Dynamic IDs should be penalized."""
    node = {"node_id": "test2", "visible": True}
    
    static_id = {"type": "css", "value": "#login-btn", "prov": "id", "dynamic": False}
    dynamic_id = {"type": "css", "value": "#btn-123456", "prov": "id", "dynamic": True}
    
    static_score = score_dom_candidate(static_id, node, "login", match_count=1)
    dynamic_score = score_dom_candidate(dynamic_id, node, "login", match_count=1)
    
    assert static_score > dynamic_score


def test_unique_match_bonus():
    """Unique matches should get bonus score."""
    node = {"node_id": "test3", "visible": True}
    cand = {"type": "css", "value": "#unique-id", "prov": "id", "dynamic": False}
    
    unique_score = score_dom_candidate(cand, node, "button", match_count=1)
    non_unique_score = score_dom_candidate(cand, node, "button", match_count=5)
    
    assert unique_score > non_unique_score


def test_score_capped():
    """Scores should be capped between 0.0 and 1.0."""
    node = {"node_id": "test4", "visible": True}
    cand = {"type": "css", "value": "#test", "prov": "aria", "dynamic": False}
    
    score = score_dom_candidate(cand, node, "test", match_count=1)
    
    assert 0.0 <= score <= 1.0


def test_match_node_to_target():
    """Test node matching to target description."""
    node = {
        "semantic_label": None,
        "aria_label": "Search",
        "text": "Search for products",
        "attributes": {"placeholder": "Enter search term"}
    }
    
    assert match_node_to_target(node, "search") == True
    assert match_node_to_target(node, "Search for products") == True
    assert match_node_to_target(node, "login") == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
