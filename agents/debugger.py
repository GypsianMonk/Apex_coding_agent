"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Debugger Agent
 Diagnoses test failures and produces surgical code patches.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import time

from agents.base import BaseAgent
from core.state import AgentRole, ApexState, DebugPatch


class DebuggerAgent(BaseAgent):
    """
    Surgical debugger that:
    1. Analyzes test failures and error traces
    2. Identifies root cause
    3. Produces minimal patches
    4. Applies patches to generated files
    """

    def __init__(self):
        super().__init__(AgentRole.DEBUGGER)

    async def execute(self, state: ApexState) -> ApexState:
        start = time.monotonic()
        state.debug_loop_count += 1
        self.log.info("debugger.start", loop=state.debug_loop_count)

        if not state.test_results or not state.test_results.failures:
            self.log.info("debugger.no_failures")
            state.needs_debug = False
            return state

        # Build context for the debugger
        files_text = "\n\n".join(
            f"=== {f.path} ===\n```{f.language}\n{f.content}\n```"
            for f in state.generated_files
        )

        failures_text = json.dumps(state.test_results.failures, indent=2)
        stderr = state.test_results.stderr[:3000] if state.test_results.stderr else "No stderr"

        prompt = f"""Debug these test failures and produce surgical patches.

FAILING TESTS:
{failures_text}

STDERR/TRACEBACK:
{stderr}

SOURCE CODE:
{files_text}

Debug loop iteration: {state.debug_loop_count} of {self.settings.max_debug_loops}

Instructions:
1. Identify the ROOT CAUSE of each failure
2. Produce MINIMAL patches — change only what's broken
3. Do NOT rewrite entire files — surgical fixes only
4. Explain WHY each fix works
5. Assess regression risk

Return JSON matching the schema from your system prompt."""

        result = await self.call_llm(prompt)

        # Parse and apply patches
        patches = []
        for patch_data in result.get("patches", []):
            patch = DebugPatch(
                file=patch_data.get("file", ""),
                original=patch_data.get("original", ""),
                fixed=patch_data.get("fixed", ""),
                explanation=patch_data.get("explanation", ""),
            )
            patches.append(patch)
            self._apply_patch(state, patch)

        state.debug_patches.extend(patches)

        # Check if we should continue debugging
        if state.debug_loop_count >= self.settings.max_debug_loops:
            self.log.warning("debugger.max_loops_reached", loops=state.debug_loop_count)
            state.needs_debug = False  # Stop debug loop, let failure handler decide
        else:
            # Will re-test after patching
            state.needs_debug = True

        duration = time.monotonic() - start
        meta = result.get("_meta", {})
        state.add_trace(
            AgentRole.DEBUGGER, "debug_patch", duration,
            tokens=meta.get("tokens", 0), cost=meta.get("cost", 0.0),
            details=f"Applied {len(patches)} patches (loop {state.debug_loop_count})",
        )
        self.log.info("debugger.complete", patches=len(patches), loop=state.debug_loop_count)
        return state

    def _apply_patch(self, state: ApexState, patch: DebugPatch) -> None:
        """Apply a patch to the matching generated file."""
        for file in state.generated_files:
            if file.path == patch.file or file.path.endswith(patch.file):
                if patch.original in file.content:
                    file.content = file.content.replace(patch.original, patch.fixed, 1)
                    self.log.info("debugger.patch_applied", file=file.path)
                else:
                    self.log.warning(
                        "debugger.patch_no_match",
                        file=file.path,
                        original_snippet=patch.original[:80],
                    )
                return
        self.log.warning("debugger.file_not_found", target=patch.file)
