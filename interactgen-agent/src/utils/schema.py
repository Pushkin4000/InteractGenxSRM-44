"""
Data schemas for InteractGen multi-agent system.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box coordinates for an element."""
    x: float
    y: float
    width: float = Field(alias="w")
    height: float = Field(alias="h")

    class Config:
        populate_by_name = True


class Candidate(BaseModel):
    """Selector candidate for an element."""
    type: str  # "css" or "xpath"
    value: str
    prov: str  # Provenance: "id", "aria", "class", "text", etc.
    score: float
    dynamic: Optional[bool] = False


class Node(BaseModel):
    """DOM node representation."""
    node_id: str
    tag: str
    text: str
    attributes: Dict[str, str]
    aria_label: Optional[str] = None
    xpath: str
    css_path: str
    bounding_box: BoundingBox
    visible: bool
    semantic_label: Optional[str] = None
    candidates: List[Candidate]
    parent_id: Optional[str] = None


class Snapshot(BaseModel):
    """Complete page snapshot."""
    url: str
    timestamp: float
    nodes: List[Node]
    ax_tree: Optional[Dict[str, Any]] = None


class Validator(BaseModel):
    """Step validator."""
    type: str  # "presence", "value_equals", "url_contains", "text_contains"
    value: Optional[str] = None
    text_contains: Optional[str] = None


class SemanticStep(BaseModel):
    """Semantic step for automation."""
    step_id: str
    action: str  # "navigate", "click", "type", "scroll", "extract"
    target: str  # Semantic description or URL
    value: Optional[str] = None
    expect: Optional[Validator] = None
    visual_hint: Optional[str] = None  # For vision-based matching


class RankedCandidate(BaseModel):
    """Ranked selector candidate."""
    node_id: str
    type: str
    value: str
    match_count: int
    score: float
    visual_score: Optional[float] = None


class StepResult(BaseModel):
    """Execution result for a step."""
    step_id: str
    ok: bool
    used_candidate: Optional[RankedCandidate] = None
    time_ms: float
    reason: Optional[str] = None
    screenshot_path: Optional[str] = None


class ExecutionSession(BaseModel):
    """Execution session state."""
    session_id: str
    url: str
    query: str
    steps: List[SemanticStep]
    results: List[StepResult]
    status: str  # "pending", "running", "completed", "failed"
