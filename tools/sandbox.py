"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Code Execution Sandbox
 Secure subprocess execution with timeout, memory limits,
 and optional Docker isolation.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import psutil
import structlog

from core.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionResult:
    """Result of a sandboxed code execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_seconds: float = 0.0
    timed_out: bool = False
    memory_exceeded: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.memory_exceeded


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""
    timeout_seconds: int = 30
    max_memory_mb: int = 512
    use_docker: bool = False
    docker_image: str = "python:3.12-slim"
    working_dir: Optional[Path] = None
    env_vars: dict[str, str] = field(default_factory=dict)
    allowed_imports: Optional[list[str]] = None  # None = all allowed


class CodeSandbox:
    """
    Secure code execution sandbox with two backends:
    1. Subprocess (default) — fast, local, with resource limits
    2. Docker (optional) — full isolation, network disabled

    Usage:
        sandbox = CodeSandbox()
        result = await sandbox.execute("print('hello')", language="python")
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        settings = get_settings()
        self.config = config or SandboxConfig(
            timeout_seconds=settings.sandbox_timeout_seconds,
            max_memory_mb=settings.sandbox_max_memory_mb,
            use_docker=settings.sandbox_use_docker,
            docker_image=settings.sandbox_docker_image,
            working_dir=settings.workspace_dir,
        )
        self._is_windows = platform.system() == "Windows"

    async def execute(
        self,
        code: str,
        language: str = "python",
        filename: Optional[str] = None,
        stdin: str = "",
    ) -> ExecutionResult:
        """Execute code in the sandbox."""
        log = logger.bind(language=language, code_length=len(code))
        log.info("sandbox.execute.start")

        try:
            if self.config.use_docker:
                result = await self._execute_docker(code, language, filename, stdin)
            else:
                result = await self._execute_subprocess(code, language, filename, stdin)

            log.info(
                "sandbox.execute.complete",
                exit_code=result.exit_code,
                duration=result.duration_seconds,
                success=result.success,
            )
            return result

        except Exception as exc:
            log.error("sandbox.execute.error", error=str(exc))
            return ExecutionResult(
                stderr=str(exc),
                exit_code=-1,
                error=str(exc),
            )

    async def execute_tests(
        self,
        test_code: str,
        source_files: dict[str, str],
        framework: str = "pytest",
    ) -> ExecutionResult:
        """
        Execute a test suite against source files.
        Creates a temporary directory with all files, then runs the test framework.
        """
        with tempfile.TemporaryDirectory(prefix="apex_test_") as tmpdir:
            tmp_path = Path(tmpdir)

            # Write source files
            for filepath, content in source_files.items():
                file_path = tmp_path / filepath
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")

            # Write test file
            test_path = tmp_path / "test_generated.py"
            test_path.write_text(test_code, encoding="utf-8")

            # Build command
            if framework == "pytest":
                cmd = ["python", "-m", "pytest", str(test_path), "-v", "--tb=short", "--no-header"]
            elif framework == "unittest":
                cmd = ["python", "-m", "unittest", str(test_path), "-v"]
            else:
                cmd = ["python", str(test_path)]

            return await self._run_process(
                cmd,
                cwd=str(tmp_path),
                env={**os.environ, "PYTHONPATH": str(tmp_path)},
            )

    async def _execute_subprocess(
        self,
        code: str,
        language: str,
        filename: Optional[str],
        stdin: str,
    ) -> ExecutionResult:
        """Execute code in a subprocess with resource limits."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=self._get_extension(language),
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            cmd = self._build_command(language, temp_path)
            return await self._run_process(
                cmd,
                stdin_data=stdin,
                cwd=str(self.config.working_dir or Path.cwd()),
            )
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    async def _execute_docker(
        self,
        code: str,
        language: str,
        filename: Optional[str],
        stdin: str,
    ) -> ExecutionResult:
        """Execute code inside a Docker container with strict isolation."""
        with tempfile.TemporaryDirectory(prefix="apex_docker_") as tmpdir:
            # Write code to temp file
            ext = self._get_extension(language)
            code_file = Path(tmpdir) / f"main{ext}"
            code_file.write_text(code, encoding="utf-8")

            cmd = [
                "docker", "run",
                "--rm",
                "--network=none",                           # No network access
                f"--memory={self.config.max_memory_mb}m",   # Memory limit
                "--cpus=1.0",                                # CPU limit
                "--read-only",                               # Read-only filesystem
                "--tmpfs=/tmp:size=64m",                     # Writable /tmp
                "-v", f"{tmpdir}:/code:ro",                  # Mount code read-only
                "-w", "/code",
                self.config.docker_image,
                *self._build_command(language, f"/code/main{ext}"),
            ]

            return await self._run_process(cmd, stdin_data=stdin)

    async def _run_process(
        self,
        cmd: list[str],
        stdin_data: str = "",
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> ExecutionResult:
        """Run a subprocess with timeout and resource monitoring."""
        start_time = time.monotonic()
        result = ExecutionResult()

        try:
            # Set resource limits on Unix
            preexec = None
            if not self._is_windows:
                import resource

                def set_limits():
                    # Memory limit (bytes)
                    mem_bytes = self.config.max_memory_mb * 1024 * 1024
                    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
                    # CPU time limit
                    resource.setrlimit(
                        resource.RLIMIT_CPU,
                        (self.config.timeout_seconds, self.config.timeout_seconds),
                    )

                preexec = set_limits

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                cwd=cwd,
                env=env,
                preexec_fn=preexec,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(
                        input=stdin_data.encode() if stdin_data else None
                    ),
                    timeout=self.config.timeout_seconds,
                )
                result.stdout = stdout_bytes.decode("utf-8", errors="replace")
                result.stderr = stderr_bytes.decode("utf-8", errors="replace")
                result.exit_code = proc.returncode or 0

            except asyncio.TimeoutError:
                # Kill the process tree
                try:
                    parent = psutil.Process(proc.pid)
                    for child in parent.children(recursive=True):
                        child.kill()
                    parent.kill()
                except (psutil.NoSuchProcess, ProcessLookupError):
                    pass

                result.timed_out = True
                result.exit_code = -9
                result.stderr = (
                    f"Execution timed out after {self.config.timeout_seconds}s"
                )

        except MemoryError:
            result.memory_exceeded = True
            result.exit_code = -7
            result.stderr = (
                f"Memory limit exceeded ({self.config.max_memory_mb}MB)"
            )

        except Exception as exc:
            result.error = str(exc)
            result.exit_code = -1
            result.stderr = f"Sandbox error: {exc}"

        result.duration_seconds = round(time.monotonic() - start_time, 3)
        return result

    @staticmethod
    def _build_command(language: str, filepath: str) -> list[str]:
        """Build the execution command for the given language."""
        commands = {
            "python": ["python", "-u", filepath],
            "javascript": ["node", filepath],
            "typescript": ["npx", "ts-node", filepath],
            "bash": ["bash", filepath],
            "ruby": ["ruby", filepath],
            "go": ["go", "run", filepath],
            "rust": ["rustc", filepath, "-o", "/tmp/apex_rust_out", "&&", "/tmp/apex_rust_out"],
        }
        if language not in commands:
            raise ValueError(f"Unsupported language: {language}")
        return commands[language]

    @staticmethod
    def _get_extension(language: str) -> str:
        """Get file extension for the given language."""
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "bash": ".sh",
            "ruby": ".rb",
            "go": ".go",
            "rust": ".rs",
        }
        return extensions.get(language, ".txt")
