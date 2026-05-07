"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Failure Handler Agent
 Dead-letter queue, graceful degradation, and escalation.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import time

from agents.base import BaseAgent
from core.state import AgentRole, ApexState, FailureType, TaskStatus


class FailureHandlerAgent(BaseAgent):
    """
    Last line of defense. Handles:
    1. Classifying failure types
    2. Determining retry vs escalate vs skip
    3. Producing partial results when possible
    4. Building incident reports
    """

    def __init__(self):
        super().__init__(AgentRole.FAILURE_HANDLER)

    async def execute(self, state: ApexState) -> ApexState:
        start = time.monotonic()
        self.log.info("failure_handler.start", failure_count=len(state.failures))

        if not state.failures:
            self.log.info("failure_handler.no_failures")
            return state

        # Build failure context
        failures_text = json.dumps(
            [f.model_dump() for f in state.failures[-5:]],  # Last 5 failures
            indent=2, default=str,
        )

        # Include what we DO have
        partial_results = {
            "has_requirements": state.requirements is not None,
            "has_architecture": state.architecture is not None,
            "generated_files": len(state.generated_files),
            "review_score": state.review_score,
            "tests_passed": state.test_results.passed if state.test_results else 0,
            "tests_failed": state.test_results.failed if state.test_results else 0,
            "debug_loops": state.debug_loop_count,
        }

        prompt = f"""Analyze these failures and determine recovery strategy.

FAILURES:
{failures_text}

PARTIAL RESULTS AVAILABLE:
{json.dumps(partial_results, indent=2)}

ORIGINAL REQUEST:
{state.user_request}

Determine:
1. Failure classification (type, severity, retryable)
2. Recovery strategy (retry with simplified prompt, escalate, skip, or deliver partial result)
3. If retrying, produce a simplified version of the original prompt
4. If delivering partial, assemble the best output from what we have

Return JSON matching the schema from your system prompt."""

        result = await self.call_llm(prompt)

        recovery = result.get("recovery_strategy", {})
        action = recovery.get("action", "partial_result")

        if action == "retry" and state.retry_count < self.settings.max_retry_attempts:
            state.retry_count += 1
            state.needs_debug = False
            # Reset for retry with simplified approach
            state.generated_files = []
            state.test_results = None
            state.review_result = None
            state.debug_loop_count = 0
            self.log.info("failure_handler.retry", attempt=state.retry_count)

        elif action == "partial_result" or action == "skip":
            # Deliver whatever we have
            state.status = TaskStatus.COMPLETED
            state.needs_debug = False
            state.final_output = self._assemble_partial_output(state, result)
            self.log.info("failure_handler.partial_result")

        else:
            # Escalate — mark as failed
            state.status = TaskStatus.FAILED
            state.needs_debug = False
            state.final_output = {
                "status": "failed",
                "reason": recovery.get("description", "Unrecoverable failure"),
                "incident_report": result.get("incident_report", {}),
                "partial_files": [f.path for f in state.generated_files],
            }
            self.log.error("failure_handler.escalated")

        duration = time.monotonic() - start
        meta = result.get("_meta", {})
        state.add_trace(
            AgentRole.FAILURE_HANDLER, f"failure_handling_{action}", duration,
            tokens=meta.get("tokens", 0), cost=meta.get("cost", 0.0),
        )
        return state

    def _assemble_partial_output(self, state: ApexState, handler_result: dict) -> dict:
        """Assemble the best possible output from partial state."""
        output = {
            "status": "partial",
            "warning": "Some pipeline stages failed. Delivering best available result.",
            "files": [],
            "requirements": state.requirements,
            "architecture": state.architecture,
        }

        for f in state.generated_files:
            output["files"].append({
                "path": f.path,
                "content": f.content,
                "language": f.language,
            })

        if state.review_result:
            output["review"] = {
                "score": state.review_score,
                "verdict": state.review_verdict.value if state.review_verdict else "N/A",
            }

        if state.test_results:
            output["tests"] = {
                "passed": state.test_results.passed,
                "failed": state.test_results.failed,
                "total": state.test_results.total,
            }

        return output
