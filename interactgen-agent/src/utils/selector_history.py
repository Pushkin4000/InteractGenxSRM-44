"""
Selector history tracking for learning from successful selectors.
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path


class SelectorHistory:
    """File-based JSON store for selector success tracking."""
    
    def __init__(self, history_file: str = "logs/selector_history.json"):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save(self):
        """Save history to file."""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)
    
    def get_success_count(self, node_id: str, selector: str) -> int:
        """Get success count for a selector."""
        key = f"{node_id}:{selector}"
        entry = self.data.get(key, {})
        return entry.get("success_count", 0)
    
    def update_success(self, node_id: str, selector: str, ok: bool):
        """Update selector success/failure."""
        key = f"{node_id}:{selector}"
        if key not in self.data:
            self.data[key] = {
                "node_id": node_id,
                "selector": selector,
                "success_count": 0,
                "failure_count": 0,
                "last_success_ts": None,
                "last_failure_ts": None
            }
        
        entry = self.data[key]
        if ok:
            entry["success_count"] += 1
            entry["last_success_ts"] = datetime.now().isoformat()
        else:
            entry["failure_count"] += 1
            entry["last_failure_ts"] = datetime.now().isoformat()
        
        self._save()
    
    def get_boost_score(self, node_id: str, selector: str) -> float:
        """Get boost score based on success history."""
        success_count = self.get_success_count(node_id, selector)
        return 0.15 if success_count > 0 else 0.0


# Global instance
_history = None

def get_history() -> SelectorHistory:
    """Get global selector history instance."""
    global _history
    if _history is None:
        _history = SelectorHistory()
    return _history


def get_success_count(node_id: str, selector: str) -> int:
    """Get success count for a selector."""
    return get_history().get_success_count(node_id, selector)


def update_success(node_id: str, selector: str, ok: bool):
    """Update selector success/failure."""
    get_history().update_success(node_id, selector, ok)


def get_boost_score(node_id: str, selector: str) -> float:
    """Get boost score based on success history."""
    return get_history().get_boost_score(node_id, selector)
