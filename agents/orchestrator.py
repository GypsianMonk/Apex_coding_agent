"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Orchestrator Agent
 Decomposes user requests into a DAG of subtasks and routes them.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from agents.base import BaseAgent
from core.state import AgentRole, ApexState, SubTask, TaskStatus

logger = structlog.get_logger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    The brain of APEX. Takes a user request and:
    1. Analyzes complexity
    2. Decomposes into a DAG of subtasks
    3. Assigns agents with proper dependency ordering
    4. Returns the execution plan in state
    """

    def __init__(self):
        super().__init__(AgentRole.ORCHESTRATOR)

    async def execute(self, state: ApexState) -> ApexState:
        start = time.monotonic()
        self.log.info("orchestrator.start", request_length=len(state.user_request))

        prompt = self._build_prompt(state)
        result = await self.call_llm(prompt)

        if result.get("_parse_error"):
            # Fallback: create a simple linear pipeline
            self.log.warning("orchestrator.fallback_pipeline")
            state = self._create_default_pipeline(state)
        else:
            state.complexity_score = float(result.get("complexity_score", 5.0))
            state.subtasks = self._parse_subtasks(result)

        duration = time.monotonic() - start
        meta = result.get("_meta", {})
        state.add_trace(
            AgentRole.ORCHESTRATOR,
            "task_decomposition",
            duration,
            tokens=meta.get("tokens", 0),
            cost=meta.get("cost", 0.0),
        )

        self.log.info(
            "orchestrator.complete",
            subtask_count=len(state.subtasks),
            complexity=state.complexity_score,
            duration=round(duration, 2),
        )
        return state

    def _build_prompt(self, state: ApexState) -> str:
        context = ""
        if state.project_context:
            context = f"\n\nProject Context:\n{state.project_context}"

        return f"""Decompose this coding task into a DAG of subtasks.

USER REQUEST:
{state.user_request}
{context}

Analyze the complexity and produce an execution plan. Remember:
- analyst and architect run in PARALLEL (tier 1)
- codegen depends on architect (tier 2)
- reviewer and tester depend on codegen (tier 3)
- debugger only if tests fail (tier 4)

Return valid JSON with the schema from your system prompt."""

    def _parse_subtasks(self, result: dict[str, Any]) -> list[SubTask]:
        subtasks = []
        for item in result.get("subtasks", []):
            try:
                agent = AgentRole(item.get("agent", "codegen"))
                subtasks.append(SubTask(
                    id=item.get("id", f"st-{len(subtasks)}"),
                    agent=agent,
                    description=item.get("description", ""),
                    depends_on=item.get("depends_on", []),
                    priority=item.get("priority", 3),
                    status=TaskStatus.PENDING,
                ))
            except (ValueError, KeyError) as exc:
                self.log.warning("orchestrator.skip_subtask", error=str(exc), item=item)
        return subtasks

    def _create_default_pipeline(self, state: ApexState) -> ApexState:
        """Fallback: create a standard linear pipeline."""
        state.complexity_score = 5.0
        state.subtasks = [
            SubTask(id="st-analyst", agent=AgentRole.ANALYST, description="Analyze requirements", depends_on=[], priority=1),
            SubTask(id="st-architect", agent=AgentRole.ARCHITECT, description="Design architecture", depends_on=[], priority=1),
            SubTask(id="st-codegen", agent=AgentRole.CODEGEN, description="Generate code", depends_on=["st-architect"], priority=2),
            SubTask(id="st-reviewer", agent=AgentRole.REVIEWER, description="Review code quality", depends_on=["st-codegen"], priority=3),
            SubTask(id="st-tester", agent=AgentRole.TESTER, description="Run tests", depends_on=["st-codegen"], priority=3),
        ]
        return state
