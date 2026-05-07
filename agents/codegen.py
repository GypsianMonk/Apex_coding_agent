"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Code Generator Agent
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import hashlib
import json
import time

from agents.base import BaseAgent
from core.state import AgentRole, ApexState, FileArtifact


class CodeGenAgent(BaseAgent):
    """Generates production-quality code files following architecture specs."""

    def __init__(self):
        super().__init__(AgentRole.CODEGEN)

    async def execute(self, state: ApexState) -> ApexState:
        start = time.monotonic()
        self.log.info("codegen.start")

        arch_text = json.dumps(state.architecture, indent=2) if state.architecture else "No architecture provided."
        req_text = json.dumps(state.requirements, indent=2) if state.requirements else "No requirements provided."

        # If we have debug patches, include them for re-generation
        patch_context = ""
        if state.debug_patches:
            patches = [
                f"File: {p.file}\nBug: {p.original}\nFix: {p.fixed}\nReason: {p.explanation}"
                for p in state.debug_patches
            ]
            patch_context = f"\n\nPREVIOUS BUG FIXES TO INCORPORATE:\n" + "\n---\n".join(patches)

        prompt = f"""Generate complete, production-ready code files.

USER REQUEST:
{state.user_request}

ARCHITECTURE SPEC:
{arch_text}

REQUIREMENTS:
{req_text}
{patch_context}

Rules:
1. Write COMPLETE files — no placeholders, no TODOs, no stubs, no "..."
2. Every file must be importable and runnable
3. Include ALL imports, type hints, docstrings, and error handling
4. Follow PEP 8 and Python best practices
5. Handle edge cases identified in requirements
6. If incorporating bug fixes, ensure the patched logic is correct

Return valid JSON with the "files" array from your system prompt schema.
Each file must have: path, content, language, description."""

        result = await self.call_llm(prompt, max_tokens=self.settings.apex_max_tokens)

        # Parse generated files
        files = []
        for file_data in result.get("files", []):
            content = file_data.get("content", "")
            files.append(FileArtifact(
                path=file_data.get("path", f"generated_{len(files)}.py"),
                content=content,
                language=file_data.get("language", "python"),
                description=file_data.get("description", ""),
                checksum=hashlib.sha256(content.encode()).hexdigest()[:16],
            ))

        state.generated_files = files

        duration = time.monotonic() - start
        meta = result.get("_meta", {})
        state.add_trace(
            AgentRole.CODEGEN, "code_generation", duration,
            tokens=meta.get("tokens", 0), cost=meta.get("cost", 0.0),
            details=f"Generated {len(files)} files",
        )
        self.log.info("codegen.complete", file_count=len(files), duration=round(duration, 2))
        return state
