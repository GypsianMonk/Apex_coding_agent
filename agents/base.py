"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Base Agent
 Abstract base class with real Anthropic Claude API integration,
 retry logic, token tracking, and structured output parsing.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import anthropic
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from core.config import get_settings, SYSTEM_PROMPTS
from core.state import AgentRole, ApexState, FailureType
from monitoring.telemetry import TOKENS_USED, LLM_LATENCY, track_duration

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """
    Abstract base for all APEX agents.

    Every agent:
    1. Has a role and system prompt
    2. Calls Claude API with structured output
    3. Tracks tokens, cost, and duration
    4. Retries on transient failures
    5. Falls back to failure_handler on permanent errors
    """

    def __init__(self, role: AgentRole):
        self.role = role
        self.settings = get_settings()
        self.system_prompt = SYSTEM_PROMPTS.get(role.value, "")
        self._client: Optional[anthropic.AsyncAnthropic] = None
        self.log = logger.bind(agent=role.value)

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self.settings.anthropic_api_key,
            )
        return self._client

    @abstractmethod
    async def execute(self, state: ApexState) -> ApexState:
        """Execute this agent's task and return updated state."""
        ...

    async def call_llm(
        self,
        user_message: str,
        system_override: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Call Claude API and parse the JSON response.
        Includes retry logic, token tracking, and cost calculation.
        """
        system = system_override or self.system_prompt
        temp = temperature if temperature is not None else self.settings.apex_temperature
        tokens = max_tokens or self.settings.apex_max_tokens

        self.log.info("llm.call.start", model=self.settings.apex_model)
        start = time.monotonic()

        try:
            response = await self._call_with_retry(system, user_message, temp, tokens)
            duration = time.monotonic() - start

            # Extract text content
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            # Track metrics
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            cost = self._calculate_cost(input_tokens, output_tokens)

            TOKENS_USED.labels(agent=self.role.value, model=self.settings.apex_model).inc(total_tokens)
            LLM_LATENCY.labels(model=self.settings.apex_model).observe(duration)

            self.log.info(
                "llm.call.complete",
                duration=round(duration, 2),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=round(cost, 4),
            )

            # Parse JSON from response
            parsed = self._parse_json_response(text)
            parsed["_meta"] = {
                "tokens": total_tokens,
                "cost": cost,
                "duration": round(duration, 3),
                "model": self.settings.apex_model,
            }
            return parsed

        except anthropic.APIStatusError as exc:
            duration = time.monotonic() - start
            self.log.error("llm.call.api_error", error=str(exc), status=exc.status_code)
            raise
        except Exception as exc:
            duration = time.monotonic() - start
            self.log.error("llm.call.error", error=str(exc), duration=round(duration, 2))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        )),
        before_sleep=lambda retry_state: structlog.get_logger().warning(
            "llm.retry",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep,
        ),
    )
    async def _call_with_retry(
        self, system: str, user_message: str, temperature: float, max_tokens: int
    ) -> anthropic.types.Message:
        """Call Claude with automatic retry on transient failures."""
        return await self.client.messages.create(
            model=self.settings.apex_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Extract JSON from LLM response, handling markdown fences."""
        cleaned = text.strip()
        # Remove markdown code fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    pass
            # Return raw text wrapped in a dict
            self.log.warning("llm.parse.fallback", text_length=len(text))
            return {"raw_response": text, "_parse_error": True}

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate USD cost based on Claude pricing."""
        # Claude Sonnet 4 pricing (per million tokens)
        pricing = {
            "claude-sonnet-4-20250514": (3.0, 15.0),
            "claude-opus-4-20250514": (15.0, 75.0),
            "claude-haiku-3-5-20241022": (0.80, 4.0),
        }
        model = self.settings.apex_model
        input_rate, output_rate = pricing.get(model, (3.0, 15.0))
        return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000

    async def safe_execute(self, state: ApexState) -> ApexState:
        """Execute with error handling — catches failures and records them."""
        import datetime
        now_iso = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Update subtask status to IN_PROGRESS
        for task in state.subtasks:
            if task.agent == self.role and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = now_iso()
                
        with track_duration(self.role.value):
            try:
                state.current_agent = self.role
                result_state = await self.execute(state)
                # Update subtask status to COMPLETED
                for task in result_state.subtasks:
                    if task.agent == self.role and task.status == TaskStatus.IN_PROGRESS:
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = now_iso()
                return result_state
            except anthropic.APIStatusError as exc:
                failure_type = FailureType.API_ERROR
                if exc.status_code == 429:
                    failure_type = FailureType.TIMEOUT
                state.add_failure(self.role, str(exc), failure_type, retryable=True)
                self.log.error("agent.failed", error=str(exc), failure_type=failure_type.value)
                self._fail_subtasks(state, str(exc))
                return state
            except TimeoutError as exc:
                state.add_failure(self.role, "Execution timeout", FailureType.TIMEOUT, retryable=True)
                self._fail_subtasks(state, "Execution timeout")
                return state
            except MemoryError as exc:
                state.add_failure(self.role, "Out of memory", FailureType.OOM, retryable=False)
                self._fail_subtasks(state, "Out of memory")
                return state
            except Exception as exc:
                state.add_failure(self.role, str(exc), FailureType.UNKNOWN, retryable=True)
                self.log.error("agent.unexpected_error", error=str(exc), exc_info=True)
                self._fail_subtasks(state, str(exc))
                return state

    def _fail_subtasks(self, state: ApexState, error_msg: str) -> None:
        """Helper to mark matching subtasks as FAILED."""
        import datetime
        for task in state.subtasks:
            if task.agent == self.role and task.status == TaskStatus.IN_PROGRESS:
                task.status = TaskStatus.FAILED
                task.error = error_msg
                task.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
