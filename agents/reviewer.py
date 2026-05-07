"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Code Reviewer Agent
 Hybrid review: AST static analysis + LLM quality assessment.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import time

from agents.base import BaseAgent
from core.state import AgentRole, ApexState, ReviewVerdict
from tools.linter import CodeLinter


class ReviewerAgent(BaseAgent):
    """
    Two-pass code review:
    1. Pass 1 (AST) — Ruff linting + structural metrics
    2. Pass 2 (LLM) — Semantic review against quality rubric
    Combined score determines APPROVE / REQUEST_CHANGES / REJECT.
    """

    def __init__(self):
        super().__init__(AgentRole.REVIEWER)
        self.linter = CodeLinter()

    async def execute(self, state: ApexState) -> ApexState:
        start = time.monotonic()
        self.log.info("reviewer.start", file_count=len(state.generated_files))

        # ── Pass 1: AST Static Analysis ────────────────────────
        lint_results = {}
        for file in state.generated_files:
            if file.language == "python":
                lint_result = self.linter.analyze(file.content, filename=file.path)
                lint_results[file.path] = {
                    "score": lint_result.score,
                    "errors": lint_result.error_count,
                    "issues": len(lint_result.issues),
                    "summary": lint_result.summary,
                }

        # ── Pass 2: LLM Semantic Review ────────────────────────
        files_for_review = "\n\n".join(
            f"=== FILE: {f.path} ===\n```{f.language}\n{f.content}\n```"
            for f in state.generated_files
        )

        prompt = f"""Review this code against your quality rubric.

LINT ANALYSIS (automated):
{json.dumps(lint_results, indent=2)}

CODE TO REVIEW:
{files_for_review}

ORIGINAL REQUEST:
{state.user_request}

Score each file on: correctness, security, performance, maintainability, error_handling, type_safety.
Set verdict to APPROVE (score >= 7), REQUEST_CHANGES (4-7), or REJECT (< 4).
Be thorough — this is the quality gate before production."""

        result = await self.call_llm(prompt)

        # Merge lint scores with LLM review
        overall_score = float(result.get("overall_score", 5.0))
        verdict_str = result.get("verdict", "REQUEST_CHANGES")

        try:
            verdict = ReviewVerdict(verdict_str)
        except ValueError:
            verdict = ReviewVerdict.REQUEST_CHANGES if overall_score < self.settings.review_score_threshold else ReviewVerdict.APPROVE

        state.review_result = {k: v for k, v in result.items() if not k.startswith("_")}
        state.review_result["lint_analysis"] = lint_results
        state.review_score = overall_score
        state.review_verdict = verdict

        # Determine if we need debug loop
        if verdict == ReviewVerdict.REJECT:
            state.needs_debug = True

        duration = time.monotonic() - start
        meta = result.get("_meta", {})
        state.add_trace(
            AgentRole.REVIEWER, "code_review", duration,
            tokens=meta.get("tokens", 0), cost=meta.get("cost", 0.0),
            details=f"Score: {overall_score}/10, Verdict: {verdict.value}",
        )
        self.log.info("reviewer.complete", score=overall_score, verdict=verdict.value)
        return state
