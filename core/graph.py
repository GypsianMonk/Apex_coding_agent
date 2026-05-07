"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — LangGraph Execution Graph
 DAG-based orchestration with conditional routing, parallel tiers,
 debug loops, and failure escalation.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from langgraph.graph import StateGraph, END

from core.state import ApexState, TaskStatus, ReviewVerdict
from core.config import get_settings
from agents.orchestrator import OrchestratorAgent
from agents.analyst import AnalystAgent
from agents.architect import ArchitectAgent
from agents.codegen import CodeGenAgent
from agents.reviewer import ReviewerAgent
from agents.tester import TesterAgent
from agents.debugger import DebuggerAgent
from agents.optimizer import OptimizerAgent
from agents.failure_handler import FailureHandlerAgent

logger = structlog.get_logger(__name__)

# ── Agent Singletons ────────────────────────────────────────────
_orchestrator = OrchestratorAgent()
_analyst = AnalystAgent()
_architect = ArchitectAgent()
_codegen = CodeGenAgent()
_reviewer = ReviewerAgent()
_tester = TesterAgent()
_debugger = DebuggerAgent()
_optimizer = OptimizerAgent()
_failure_handler = FailureHandlerAgent()


# ═══════════════════════════════════════════════════════════════
#  Node Functions (LangGraph requires sync or async callables)
# ═══════════════════════════════════════════════════════════════

async def orchestrate_node(state: dict[str, Any]) -> dict[str, Any]:
    """Decompose task into subtasks."""
    apex_state = ApexState.model_validate(state)
    apex_state = await _orchestrator.safe_execute(apex_state)
    return apex_state.model_dump(mode="json")


async def analyze_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run analyst and architect in parallel (Tier 1)."""
    apex_state = ApexState.model_validate(state)

    # Parallel execution of analyst + architect
    analyst_task = _analyst.safe_execute(apex_state.model_copy(deep=True))
    architect_task = _architect.safe_execute(apex_state.model_copy(deep=True))

    analyst_result, architect_result = await asyncio.gather(
        analyst_task, architect_task
    )

    # Merge results back
    apex_state.requirements = analyst_result.requirements
    apex_state.architecture = architect_result.architecture
    apex_state.agent_trace.extend(analyst_result.agent_trace[len(apex_state.agent_trace):])
    apex_state.agent_trace.extend(architect_result.agent_trace[len(apex_state.agent_trace):])
    apex_state.total_tokens_used = analyst_result.total_tokens_used + architect_result.total_tokens_used
    apex_state.total_cost_usd = analyst_result.total_cost_usd + architect_result.total_cost_usd

    return apex_state.model_dump(mode="json")


async def codegen_node(state: dict[str, Any]) -> dict[str, Any]:
    """Generate code (Tier 2)."""
    apex_state = ApexState.model_validate(state)
    apex_state = await _codegen.safe_execute(apex_state)
    return apex_state.model_dump(mode="json")


async def review_node(state: dict[str, Any]) -> dict[str, Any]:
    """Review code quality (Tier 3)."""
    apex_state = ApexState.model_validate(state)
    apex_state = await _reviewer.safe_execute(apex_state)
    return apex_state.model_dump(mode="json")


async def test_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run tests (Tier 3)."""
    apex_state = ApexState.model_validate(state)
    apex_state = await _tester.safe_execute(apex_state)
    return apex_state.model_dump(mode="json")


async def debug_node(state: dict[str, Any]) -> dict[str, Any]:
    """Debug failures (Tier 4)."""
    apex_state = ApexState.model_validate(state)
    apex_state = await _debugger.safe_execute(apex_state)
    return apex_state.model_dump(mode="json")


async def optimize_node(state: dict[str, Any]) -> dict[str, Any]:
    """Optimize code (Tier 4)."""
    apex_state = ApexState.model_validate(state)
    apex_state = await _optimizer.safe_execute(apex_state)
    return apex_state.model_dump(mode="json")


async def failure_node(state: dict[str, Any]) -> dict[str, Any]:
    """Handle failures (Tier 5)."""
    apex_state = ApexState.model_validate(state)
    apex_state = await _failure_handler.safe_execute(apex_state)
    return apex_state.model_dump(mode="json")


async def finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    """Assemble final output."""
    apex_state = ApexState.model_validate(state)
    apex_state.status = TaskStatus.COMPLETED

    apex_state.final_output = {
        "status": "completed",
        "files": [
            {"path": f.path, "content": f.content, "language": f.language, "description": f.description}
            for f in apex_state.generated_files
        ],
        "review": {
            "score": apex_state.review_score,
            "verdict": apex_state.review_verdict.value if apex_state.review_verdict else "N/A",
        },
        "tests": {
            "total": apex_state.test_results.total if apex_state.test_results else 0,
            "passed": apex_state.test_results.passed if apex_state.test_results else 0,
            "failed": apex_state.test_results.failed if apex_state.test_results else 0,
        },
        "metrics": {
            "total_tokens": apex_state.total_tokens_used,
            "total_cost_usd": round(apex_state.total_cost_usd, 4),
            "total_duration_seconds": round(apex_state.total_duration_seconds, 2),
            "debug_loops": apex_state.debug_loop_count,
            "agent_trace": apex_state.agent_trace,
        },
    }

    apex_state.summary = (
        f"Generated {len(apex_state.generated_files)} files | "
        f"Review: {apex_state.review_score}/10 | "
        f"Tests: {apex_state.test_results.passed}/{apex_state.test_results.total if apex_state.test_results else 0} passed | "
        f"Cost: ${apex_state.total_cost_usd:.4f}"
    )

    logger.info("pipeline.finalized", summary=apex_state.summary)
    return apex_state.model_dump(mode="json")


# ═══════════════════════════════════════════════════════════════
#  Conditional Edge Functions (Routing Logic)
# ═══════════════════════════════════════════════════════════════

def route_after_test(state: dict[str, Any]) -> str:
    """After testing: debug if failures, optimize if clean, or finalize."""
    apex_state = ApexState.model_validate(state)
    settings = get_settings()

    # Check for fatal failures
    if apex_state.status == TaskStatus.FAILED:
        return "failure_handler"

    # If tests failed and we haven't exceeded debug loops
    if apex_state.needs_debug and apex_state.debug_loop_count < settings.max_debug_loops:
        return "debugger"

    # If tests failed but we've exhausted debug loops
    if apex_state.needs_debug and apex_state.debug_loop_count >= settings.max_debug_loops:
        return "failure_handler"

    # Tests passed — check if review score warrants optimization
    if apex_state.review_score >= settings.review_score_threshold:
        return "optimizer"

    return "finalize"


def route_after_debug(state: dict[str, Any]) -> str:
    """After debugging: re-test the patched code."""
    apex_state = ApexState.model_validate(state)
    settings = get_settings()

    if apex_state.debug_loop_count >= settings.max_debug_loops:
        return "failure_handler"

    # Re-run tests after applying patches
    return "tester"


def route_after_failure(state: dict[str, Any]) -> str:
    """After failure handling: retry pipeline or finalize."""
    apex_state = ApexState.model_validate(state)

    if apex_state.status == TaskStatus.FAILED:
        return "finalize"

    # If failure handler decided to retry
    if apex_state.retry_count > 0 and not apex_state.generated_files:
        return "analyze"

    return "finalize"


def route_after_review(state: dict[str, Any]) -> str:
    """After review: proceed to test or reject."""
    apex_state = ApexState.model_validate(state)

    if apex_state.review_verdict == ReviewVerdict.REJECT:
        # Re-generate with review feedback
        if apex_state.retry_count < get_settings().max_retry_attempts:
            apex_state.retry_count += 1
            return "codegen"
        return "failure_handler"

    return "tester"


# ═══════════════════════════════════════════════════════════════
#  Graph Builder
# ═══════════════════════════════════════════════════════════════

def build_graph() -> StateGraph:
    """
    Build the APEX execution graph.

    Flow:
    orchestrate → analyze (analyst+architect parallel)
              → codegen → review → test
                                    ↓
                              [pass] → optimize → finalize
                              [fail] → debug → test (loop)
                              [exhausted] → failure_handler → finalize
    """
    graph = StateGraph(dict)

    # ── Add Nodes ───────────────────────────────────────────────
    graph.add_node("orchestrate", orchestrate_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("codegen", codegen_node)
    graph.add_node("review", review_node)
    graph.add_node("tester", test_node)
    graph.add_node("debugger", debug_node)
    graph.add_node("optimizer", optimize_node)
    graph.add_node("failure_handler", failure_node)
    graph.add_node("finalize", finalize_node)

    # ── Linear Edges ───────────────────────────────────────────
    graph.set_entry_point("orchestrate")
    graph.add_edge("orchestrate", "analyze")
    graph.add_edge("analyze", "codegen")
    graph.add_edge("codegen", "review")
    graph.add_edge("optimizer", "finalize")
    graph.add_edge("finalize", END)

    # ── Conditional Edges ──────────────────────────────────────
    graph.add_conditional_edges("review", route_after_review, {
        "tester": "tester",
        "codegen": "codegen",
        "failure_handler": "failure_handler",
    })

    graph.add_conditional_edges("tester", route_after_test, {
        "debugger": "debugger",
        "optimizer": "optimizer",
        "failure_handler": "failure_handler",
        "finalize": "finalize",
    })

    graph.add_conditional_edges("debugger", route_after_debug, {
        "tester": "tester",
        "failure_handler": "failure_handler",
    })

    graph.add_conditional_edges("failure_handler", route_after_failure, {
        "analyze": "analyze",
        "finalize": "finalize",
    })

    return graph


def compile_graph():
    """Compile the graph for execution."""
    graph = build_graph()
    return graph.compile()
