"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Architect Agent
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import time

from agents.base import BaseAgent
from core.state import AgentRole, ApexState


class ArchitectAgent(BaseAgent):
    """Designs system architecture, file structure, data models, and API contracts."""

    def __init__(self):
        super().__init__(AgentRole.ARCHITECT)

    async def execute(self, state: ApexState) -> ApexState:
        start = time.monotonic()
        self.log.info("architect.start")

        requirements_text = json.dumps(state.requirements, indent=2) if state.requirements else "No requirements provided."

        prompt = f"""Design the architecture for this coding task.

USER REQUEST:
{state.user_request}

REQUIREMENTS (from Analyst):
{requirements_text}

Produce:
1. Architecture style (monolith, microservice, library, etc.)
2. Component breakdown with responsibilities
3. Complete file structure with descriptions
4. Data models with fields and relationships
5. API contracts (if applicable)
6. Key design decisions with rationale and alternatives considered

Return valid JSON matching the schema from your system prompt.
Be specific — every file path must be concrete, every model must have typed fields."""

        result = await self.call_llm(prompt)
        state.architecture = {k: v for k, v in result.items() if not k.startswith("_")}

        duration = time.monotonic() - start
        meta = result.get("_meta", {})
        state.add_trace(
            AgentRole.ARCHITECT, "architecture_design", duration,
            tokens=meta.get("tokens", 0), cost=meta.get("cost", 0.0),
        )
        self.log.info("architect.complete", duration=round(duration, 2))
        return state
