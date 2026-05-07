"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Requirements Analyst Agent
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import time

from agents.base import BaseAgent
from core.state import AgentRole, ApexState


class AnalystAgent(BaseAgent):
    """Extracts structured requirements, constraints, edge cases, and acceptance criteria."""

    def __init__(self):
        super().__init__(AgentRole.ANALYST)

    async def execute(self, state: ApexState) -> ApexState:
        start = time.monotonic()
        self.log.info("analyst.start")

        prompt = f"""Analyze this coding request and extract structured requirements.

USER REQUEST:
{state.user_request}

PROJECT CONTEXT:
{state.project_context or "No additional context provided."}

Extract:
1. Functional requirements (what it must DO)
2. Non-functional requirements (performance, security, scalability)
3. Constraints (language, framework, dependencies)
4. Edge cases and failure modes
5. Acceptance criteria in Given/When/Then format
6. Assumptions you are making
7. Risks you foresee

Return valid JSON matching the schema from your system prompt."""

        result = await self.call_llm(prompt)
        state.requirements = {k: v for k, v in result.items() if not k.startswith("_")}

        duration = time.monotonic() - start
        meta = result.get("_meta", {})
        state.add_trace(
            AgentRole.ANALYST, "requirements_analysis", duration,
            tokens=meta.get("tokens", 0), cost=meta.get("cost", 0.0),
        )
        self.log.info("analyst.complete", duration=round(duration, 2))
        return state
