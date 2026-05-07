"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Test Engineer Agent
 Generates test suites and executes them in the sandbox.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import time

from agents.base import BaseAgent
from core.state import AgentRole, ApexState, TestResult
from tools.sandbox import CodeSandbox
from monitoring.telemetry import SANDBOX_EXECUTIONS


class TesterAgent(BaseAgent):
    """
    Two-phase testing:
    1. Generate comprehensive tests via LLM
    2. Execute tests in sandbox and capture results
    """

    def __init__(self):
        super().__init__(AgentRole.TESTER)
        self.sandbox = CodeSandbox()

    async def execute(self, state: ApexState) -> ApexState:
        start = time.monotonic()
        self.log.info("tester.start", file_count=len(state.generated_files))

        # ── Phase 1: Generate Tests ────────────────────────────
        files_text = "\n\n".join(
            f"=== {f.path} ===\n```{f.language}\n{f.content}\n```"
            for f in state.generated_files
        )
        req_text = json.dumps(state.requirements, indent=2) if state.requirements else "None"

        prompt = f"""Generate comprehensive pytest test suites for this code.

SOURCE CODE:
{files_text}

REQUIREMENTS:
{req_text}

Generate tests covering:
1. Happy path — normal expected behavior
2. Edge cases — boundary values, empty inputs, None, large inputs
3. Error paths — invalid input, expected exceptions
4. Type checking — ensure correct types returned

Rules:
- Use pytest with descriptive test names
- Include setup/teardown where needed
- Mock external dependencies (API calls, file I/O, databases)
- Each test must be independent
- Use parametrize for multiple input variations
- Add clear assertion messages

Return JSON with test_files array. Each entry needs: path, content, test_count."""

        result = await self.call_llm(prompt)

        test_files = result.get("test_files", [])
        if not test_files:
            self.log.warning("tester.no_tests_generated")
            state.test_results = TestResult(total=0, passed=0, failed=0)
            state.needs_debug = False
            duration = time.monotonic() - start
            state.add_trace(AgentRole.TESTER, "test_generation", duration, details="No tests generated")
            return state

        # ── Phase 2: Execute Tests in Sandbox ──────────────────
        source_map = {f.path: f.content for f in state.generated_files}
        all_results = TestResult()

        for test_file in test_files:
            test_content = test_file.get("content", "")
            test_path = test_file.get("path", "test_generated.py")

            if not test_content.strip():
                continue

            self.log.info("tester.executing", test_file=test_path)

            exec_result = await self.sandbox.execute_tests(
                test_code=test_content,
                source_files=source_map,
                framework="pytest",
            )

            SANDBOX_EXECUTIONS.labels(
                language="python",
                status="success" if exec_result.success else "failure",
            ).inc()

            # Parse pytest output
            parsed = self._parse_pytest_output(exec_result.stdout, exec_result.stderr)
            all_results.total += parsed.get("total", 0)
            all_results.passed += parsed.get("passed", 0)
            all_results.failed += parsed.get("failed", 0)
            all_results.errors += parsed.get("errors", 0)
            all_results.stdout += exec_result.stdout + "\n"
            all_results.stderr += exec_result.stderr + "\n"
            all_results.duration_seconds += exec_result.duration_seconds

            if parsed.get("failures"):
                all_results.failures.extend(parsed["failures"])

        state.test_results = all_results
        state.needs_debug = all_results.failed > 0 or all_results.errors > 0

        duration = time.monotonic() - start
        meta = result.get("_meta", {})
        state.add_trace(
            AgentRole.TESTER, "test_execution", duration,
            tokens=meta.get("tokens", 0), cost=meta.get("cost", 0.0),
            details=f"Total: {all_results.total}, Passed: {all_results.passed}, Failed: {all_results.failed}",
        )
        self.log.info(
            "tester.complete",
            total=all_results.total, passed=all_results.passed,
            failed=all_results.failed, needs_debug=state.needs_debug,
        )
        return state

    def _parse_pytest_output(self, stdout: str, stderr: str) -> dict:
        """Parse pytest output to extract test counts and failures."""
        result = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "failures": []}
        output = stdout + stderr

        for line in output.split("\n"):
            line = line.strip()
            # Parse summary line: "5 passed, 2 failed, 1 error"
            if "passed" in line or "failed" in line or "error" in line:
                parts = line.split(",")
                for part in parts:
                    part = part.strip()
                    if "passed" in part:
                        try:
                            result["passed"] = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass
                    elif "failed" in part:
                        try:
                            result["failed"] = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass
                    elif "error" in part:
                        try:
                            result["errors"] = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass

            # Capture FAILED test details
            if line.startswith("FAILED"):
                result["failures"].append({
                    "test_name": line.replace("FAILED ", "").split(" -")[0],
                    "error_message": line,
                    "traceback": "",
                })

        result["total"] = result["passed"] + result["failed"] + result["errors"]
        return result
