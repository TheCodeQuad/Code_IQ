"""
Pydantic models for the repositories collection.

Maps to the MongoDB `repositories` collection in the `codeiq` database.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Status enum ──────────────────────────────────────────────────────

class RepoStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"         # Navigator is scanning files
    READING = "reading"         # Reader agent analysing code
    SEARCHING = "searching"     # Searcher agent gathering context
    WRITING = "writing"         # Writer agent generating docs
    VERIFYING = "verifying"     # Verifier agent checking quality
    EVALUATING = "evaluating"   # Evaluator scoring docs
    COMPLETED = "completed"
    FAILED = "failed"


# ── Sub-documents ────────────────────────────────────────────────────

class AgentLog(BaseModel):
    agent: str
    status: str = "pending"             # pending | in_progress | completed | failed
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    message: Optional[str] = None


class EvaluationScores(BaseModel):
    accuracy: Optional[float] = None
    completeness: Optional[float] = None
    clarity: Optional[float] = None
    consistency: Optional[float] = None
    overall_score: Optional[float] = None


# ── Repository document ─────────────────────────────────────────────

class RepositoryDoc(BaseModel):
    """
    Full schema for a document in the `repositories` collection.
    Fields align with what the frontend dashboard needs.
    """
    # Identity
    user_id: str                          # ObjectId of the owning user (as string)
    repo_name: str
    repo_url: Optional[str] = None        # None if uploaded as zip
    repo_local_path: Optional[str] = None # Server-side clone path

    # Metadata (filled by navigator)
    language: Optional[str] = None
    file_count: int = 0
    total_lines: int = 0

    # Pipeline state
    status: RepoStatus = RepoStatus.PENDING
    current_agent: Optional[str] = None
    progress_percent: int = 0
    agent_logs: List[AgentLog] = Field(default_factory=lambda: [
        AgentLog(agent="navigator"),
        AgentLog(agent="reader"),
        AgentLog(agent="searcher"),
        AgentLog(agent="writer"),
        AgentLog(agent="verifier"),
        AgentLog(agent="evaluator"),
    ])

    # Results (filled after pipeline completes)
    stats: Optional[Dict[str, Any]] = None        # AnalysisStats dict
    documentation: Optional[List[Any]] = None      # Generated docs
    evaluation: Optional[EvaluationScores] = None

    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None

    error_message: Optional[str] = None


# ── Request / Response models for the API ────────────────────────────

class RepoUploadRequest(BaseModel):
    """Body for POST /api/repos/upload"""
    repo_url: str = Field(..., description="GitHub repository URL to clone")
    user_id: str = Field(..., description="User ObjectId (from session)")


class RepoSummary(BaseModel):
    """Lightweight shape returned in list endpoints."""
    id: str
    repo_name: str
    repo_url: Optional[str] = None
    language: Optional[str] = None
    file_count: int = 0
    status: str
    progress_percent: int = 0
    current_agent: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    overall_score: Optional[float] = None


class RepoDetail(RepoSummary):
    """Full shape returned for a single repo."""
    repo_local_path: Optional[str] = None
    total_lines: int = 0
    agent_logs: List[AgentLog] = []
    stats: Optional[Dict[str, Any]] = None
    documentation: Optional[List[Any]] = None
    evaluation: Optional[EvaluationScores] = None
    error_message: Optional[str] = None