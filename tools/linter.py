"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Code Linter & Static Analysis
 Ruff integration + AST-based analysis for Python code.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import ast
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LintIssue:
    file: str
    line: int
    column: int
    code: str
    message: str
    severity: str
    fixable: bool = False


@dataclass
class ASTMetrics:
    total_lines: int = 0
    code_lines: int = 0
    functions: int = 0
    classes: int = 0
    imports: int = 0
    max_function_length: int = 0
    max_complexity: int = 0
    type_hint_coverage: float = 0.0
    docstring_coverage: float = 0.0
    issues: list[str] = field(default_factory=list)


@dataclass
class LintResult:
    issues: list[LintIssue] = field(default_factory=list)
    metrics: Optional[ASTMetrics] = None
    score: float = 10.0
    summary: str = ""

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")


class CodeLinter:
    """Ruff linting + AST structural analysis."""

    def analyze(self, code: str, language: str = "python", filename: str = "code.py") -> LintResult:
        result = LintResult()
        if language == "python":
            result.issues.extend(self._run_ruff(code, filename))
            result.metrics = self._analyze_ast(code)
        result.score = max(10.0 - sum(1.0 if i.severity == "error" else 0.3 for i in result.issues), 0.0)
        result.summary = f"Score: {result.score}/10 | {result.error_count} errors | {len(result.issues)} total issues"
        return result

    def auto_fix(self, code: str) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = f.name
        try:
            subprocess.run(["ruff", "check", "--fix", temp_path], capture_output=True, timeout=15)
            subprocess.run(["ruff", "format", temp_path], capture_output=True, timeout=15)
            return Path(temp_path).read_text(encoding="utf-8")
        except Exception:
            return code
        finally:
            try:
                Path(temp_path).unlink()
            except OSError:
                pass

    def _run_ruff(self, code: str, filename: str) -> list[LintIssue]:
        issues = []
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = f.name
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=json", "--select=E,F,W,I,N,UP,B,S", temp_path],
                capture_output=True, text=True, timeout=15,
            )
            if result.stdout.strip():
                for item in json.loads(result.stdout):
                    severity = "error" if item.get("code", "").startswith(("E", "F")) else "warning"
                    issues.append(LintIssue(
                        file=filename,
                        line=item.get("location", {}).get("row", 0),
                        column=item.get("location", {}).get("column", 0),
                        code=item.get("code", ""),
                        message=item.get("message", ""),
                        severity=severity,
                        fixable=item.get("fix", {}).get("applicability", "") == "safe",
                    ))
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        finally:
            try:
                Path(temp_path).unlink()
            except OSError:
                pass
        return issues

    def _analyze_ast(self, code: str) -> ASTMetrics:
        metrics = ASTMetrics()
        lines = code.split("\n")
        metrics.total_lines = len(lines)
        metrics.code_lines = sum(1 for l in lines if l.strip() and not l.strip().startswith("#"))
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            metrics.issues.append(f"SyntaxError: {e}")
            return metrics

        all_defs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                metrics.classes += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                metrics.functions += 1
                all_defs.append(node)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                metrics.imports += 1

        # Type hint coverage
        typed = total = 0
        for func in all_defs:
            for arg in func.args.args:
                total += 1
                if arg.annotation:
                    typed += 1
        metrics.type_hint_coverage = round(typed / total, 2) if total else 0.0

        # Docstring coverage
        documented = sum(
            1 for f in all_defs
            if f.body and isinstance(f.body[0], ast.Expr) and isinstance(f.body[0].value, ast.Constant)
        )
        metrics.docstring_coverage = round(documented / len(all_defs), 2) if all_defs else 0.0

        # Function length
        for func in all_defs:
            if hasattr(func, "end_lineno") and func.end_lineno:
                length = func.end_lineno - func.lineno
                metrics.max_function_length = max(metrics.max_function_length, length)
                if length > 50:
                    metrics.issues.append(f"Function '{func.name}' is {length} lines long")

        # Cyclomatic complexity
        cx = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                cx += 1
        metrics.max_complexity = cx
        if cx > 15:
            metrics.issues.append(f"High complexity: {cx}")

        return metrics
