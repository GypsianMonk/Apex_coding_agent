"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — LangGraph State Schema
 Typed state that flows through the entire agent graph.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    ANALYST = "analyst"
    ARCHITECT = "architect"
    CODEGEN = "codegen"
    REVIEWER = "reviewer"
    TESTER = "tester"
    DEBUGGER = "debugger"
    OPTIMIZER = "optimizer"
    FAILURE_HANDLER = "failure_handler"


class ReviewVerdict(str, Enum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    REJECT = "REJECT"


class FailureType(str, Enum):
    TIMEOUT = "timeout"
    HALLUCINATION = "hallucination"
    OOM = "oom"
    POLICY_VIOLATION = "policy_violation"
    API_ERROR = "api_error"
    UNKNOWN = "unknown"


# ── Data Models ─────────────────────────────────────────────────

class SubTask(BaseModel):
    """A single subtask in the orchestration DAG."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: AgentRole
    description: str
    depends_on: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    attempt: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class FileArtifact(BaseModel):
    """A generated code file."""
    path: str
    content: str
    language: str = "python"
    description: str = ""
    checksum: str = ""


class ReviewIssue(BaseModel):
    """A single issue found during code review."""
    severity: str  # critical, major, minor, nit
    file: str
    line: Optional[int] = None
    description: str
    suggested_fix: Optional[str] = None


class TestResult(BaseModel):
    """Results from running a test suite."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    failures: list[dict[str, Any]] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0


class DebugPatch(BaseModel):
    """A surgical code patch from the debugger."""
    file: str
    original: str
    fixed: str
    explanation: str


class FailureRecord(BaseModel):
    """Record of a failure for the dead-letter queue."""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent: AgentRole
    error: str
    context: str = ""
    failure_type: FailureType = FailureType.UNKNOWN
    retryable: bool = True
    attempt: int = 1


# ── LangGraph State ─────────────────────────────────────────────

class ApexState(BaseModel):
    """
    The central state object that flows through the LangGraph.
    Every agent reads from and writes to this state.
    """

    # ── Identity ────────────────────────────────────────────────
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── User Input ──────────────────────────────────────────────
    user_request: str = ""
    project_context: dict[str, Any] = Field(default_factory=dict)

    # ── Orchestration ───────────────────────────────────────────
    complexity_score: float = 0.0
    subtasks: list[SubTask] = Field(default_factory=list)
    current_agent: AgentRole = AgentRole.ORCHESTRATOR
    execution_tier: int = 0

    # ── Agent Outputs ───────────────────────────────────────────
    requirements: Optional[dict[str, Any]] = None
    architecture: Optional[dict[str, Any]] = None
    generated_files: list[FileArtifact] = Field(default_factory=list)
    review_result: Optional[dict[str, Any]] = None
    review_score: float = 0.0
    review_verdict: Optional[ReviewVerdict] = None
    test_results: Optional[TestResult] = None
    debug_patches: list[DebugPatch] = Field(default_factory=list)
    optimization_result: Optional[dict[str, Any]] = None

    # ── Control Flow ────────────────────────────────────────────
    status: TaskStatus = TaskStatus.PENDING
    debug_loop_count: int = 0
    retry_count: int = 0
    needs_debug: bool = False
    needs_optimization: bool = False

    # ── Failure Handling ────────────────────────────────────────
    failures: list[FailureRecord] = Field(default_factory=list)
    dead_letter_queue: list[FailureRecord] = Field(default_factory=list)

    # ── Tracing ─────────────────────────────────────────────────
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0

    # ── Final Output ────────────────────────────────────────────
    final_output: Optional[dict[str, Any]] = None
    summary: str = ""

    def add_trace(
        self,
        agent: AgentRole,
        action: str,
        duration: float,
        tokens: int = 0,
        cost: float = 0.0,
        success: bool = True,
        details: str = "",
    ) -> None:
        """Append an entry to the agent execution trace."""
        self.agent_trace.append({
            "agent": agent.value,
            "action": action,
            "duration_seconds": round(duration, 3),
            "tokens": tokens,
            "cost_usd": round(cost, 6),
            "success": success,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.total_tokens_used += tokens
        self.total_cost_usd += cost
        self.total_duration_seconds += duration

    def add_failure(
        self,
        agent: AgentRole,
        error: str,
        failure_type: FailureType = FailureType.UNKNOWN,
        retryable: bool = True,
    ) -> None:
        """Record a failure and optionally add to dead-letter queue."""
        record = FailureRecord(
            agent=agent,
            error=error,
            failure_type=failure_type,
            retryable=retryable,
            attempt=self.retry_count + 1,
        )
        self.failures.append(record)
        if not retryable:
            self.dead_letter_queue.append(record)

    def get_pending_subtasks(self) -> list[SubTask]:
        """Return subtasks that are ready to execute (deps satisfied)."""
        completed_ids = {
            st.id for st in self.subtasks if st.status == TaskStatus.COMPLETED
        }
        return [
            st
            for st in self.subtasks
            if st.status == TaskStatus.PENDING
            and all(dep in completed_ids for dep in st.depends_on)
        ]

    def to_snapshot(self) -> dict[str, Any]:
        """Serialize state for Redis persistence."""
        return self.model_dump(mode="json")

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "ApexState":
        """Restore state from a Redis snapshot."""
        return cls.model_validate(data)
