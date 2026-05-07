"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Optimizer Agent
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import time

from agents.base import BaseAgent
from core.state import AgentRole, ApexState


class OptimizerAgent(BaseAgent):
    """Analyzes code for performance hotspots and applies optimizations."""

    def __init__(self):
        super().__init__(AgentRole.OPTIMIZER)

    async def execute(self, state: ApexState) -> ApexState:
        start = time.monotonic()
        self.log.info("optimizer.start")

        files_text = "\n\n".join(
            f"=== {f.path} ===\n```{f.language}\n{f.content}\n```"
            for f in state.generated_files
        )

        prompt = f"""Analyze this code for performance optimizations.

SOURCE CODE:
{files_text}

Analyze:
1. Algorithmic complexity — O(n²) → O(n log n) opportunities
2. Memory — unnecessary copies, large allocations, generator opportunities
3. I/O — batching, caching, connection pooling
4. Concurrency — async opportunities, thread safety
5. Dead code — unused imports, unreachable branches

Only suggest optimizations with REAL impact. Don't micro-optimize.
Return JSON matching the schema from your system prompt."""

        result = await self.call_llm(prompt)
        state.optimization_result = {k: v for k, v in result.items() if not k.startswith("_")}

        # Apply optimizations to files
        for opt in result.get("optimizations", []):
            target_file = opt.get("file", "")
            original = opt.get("original", "")
            optimized = opt.get("optimized", "")
            if original and optimized:
                for file in state.generated_files:
                    if file.path == target_file or file.path.endswith(target_file):
                        if original in file.content:
                            file.content = file.content.replace(original, optimized, 1)
                            self.log.info("optimizer.applied", file=file.path)

        duration = time.monotonic() - start
        meta = result.get("_meta", {})
        state.add_trace(
            AgentRole.OPTIMIZER, "optimization", duration,
            tokens=meta.get("tokens", 0), cost=meta.get("cost", 0.0),
        )
        self.log.info("optimizer.complete", duration=round(duration, 2))
        return state
