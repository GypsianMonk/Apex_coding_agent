# APEX: Technical Architecture & Design Rationale

This document provides a deep dive into the architectural decisions and implementation details of the **APEX Multi-Agent Coding System**.

---

## 1. Core Philosophy: The Tiered Agent Model

APEX does not treat LLMs as single-step generators. Instead, it views software engineering as a multi-stage refinement process. We organize our agents into **Tiers** to maximize efficiency and minimize error propagation.

### Tier 1: Discovery & Definition
- **Analyst**: Converts ambiguous user intent into a formal specification. It identifies "Implicit Requirements" (e.g., thread safety, input validation) that the user might have missed.
- **Architect**: Translates specs into a concrete file-system blueprint. It handles the "Mental Model" of the codebase before a single line of code is written.

### Tier 2: Implementation
- **CodeGen**: A high-precision generator that consumes the Spec (Analyst) and Blueprint (Architect). It is capable of merging surgical patches provided by the Debugger in recursive loops.

### Tier 3: Quality Gate & Verification
- **Reviewer**: Performs a hybrid evaluation. It uses **Ruff** for strict linting and custom **AST visitors** for complexity analysis, followed by an LLM pass for "Semantic Quality" (logic flow, naming clarity).
- **Tester**: Automatically generates **Pytest** suites based on the initial Spec. It ensures that the code doesn't just "look good" but actually works.

### Tier 4: Autonomous Repair
- **Debugger**: Triggered only on test failure. It analyzes execution tracebacks, identifies root causes, and generates targeted code modifications.
- **Optimizer**: Triggered on success. It reviews code for algorithmic efficiency and applies Pythonic optimizations.

---

## 2. State Management via LangGraph

APEX uses a central `ApexState` object (typed via Pydantic) that flows through the LangGraph DAG. This ensures:
- **Reproducibility**: The entire state can be serialized to Redis at any node.
- **Persistence**: If the system crashes, it can resume from the last successful node.
- **Traceability**: Every agent's input, output, and token usage is captured in the state.

### State Schema Highlights:
```python
class ApexState(TypedDict):
    request: str                  # Original user prompt
    spec: Optional[RequirementSpec] # From Analyst
    blueprint: Optional[Blueprint]  # From Architect
    artifacts: List[CodeFile]      # Current codebase
    tests: List[CodeFile]          # Generated tests
    review: Optional[ReviewResult] # Reviewer output
    test_results: Optional[TestRun] # Sandbox output
    iterations: int               # Debug loop counter
    telemetry: TelemetryData       # Token tracking & cost
```

---

## 3. The Execution Sandbox

To safely execute agent-generated code, APEX implements a dual-backend sandbox:

### Subprocess Backend (Default)
Uses `subprocess.Popen` with the following safety primitives:
- **Timeout**: Hard kill after `SANDBOX_TIMEOUT` seconds.
- **Memory Limit**: Monitored via `psutil`. If a process exceeds its quota, the entire process tree is terminated.
- **Cleanup**: Recursive process tree termination to prevent orphaned "zombie" processes.

### Docker Backend (Isolated)
For high-security environments, APEX spins up ephemeral Docker containers with:
- `network_disabled=True`
- `read_only=True` (except for `/tmp`)
- `mem_limit="512m"`
- `pids_limit=50`

---

## 4. Observability Stack

APEX is designed for "Day 2 Operations." It isn't a black box.

### Metrics (Prometheus)
We track business and technical KPIs:
- `apex_agent_latency_seconds`: Histogram of per-agent execution time.
- `apex_token_usage_total`: Counter for cost monitoring.
- `apex_review_score`: Gauge tracking code quality trends.
- `apex_sandbox_failures_total`: Counter for tracking system reliability.

### Tracing (OpenTelemetry + Jaeger)
Every request generates a `TraceID`. Each agent execution is a `Span`. This allows developers to:
1. Identify which agent is the bottleneck.
2. See exactly what the LLM received and replied with at each step.
3. Visualize the "Debug Loop" cycles.

---

## 5. Security & Authentication

- **API Key Middleware**: All REST/WebSocket endpoints require an `X-API-Key` header.
- **Sanitized Outputs**: LLM outputs are stripped of markdown fences and validated against Pydantic schemas before being trusted by the system.
- **Input Filtering**: User requests are scanned for prompt injection patterns before entering the Orchestrator.

---
