<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f0c29,50:302b63,100:24243e&height=220&section=header&text=APEX&fontSize=90&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Autonomous%20Multi-Agent%20Coding%20System&descAlignY=60&descSize=20&descColor=a78bfa" width="100%"/>

<!-- Typing SVG -->
[![Typing SVG](https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=20&pause=1000&color=A78BFA&center=true&vCenter=true&width=750&lines=9+Specialist+Agents+%7C+Self-Correcting+DAG+Architecture;Analyze+%E2%86%92+Architect+%E2%86%92+Implement+%E2%86%92+Review+%E2%86%92+Test+%E2%86%92+Optimize;Production-Grade+AI+Engineering+%F0%9F%9A%80)](https://git.io/typing-svg)

<br/>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-FF6B35?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![Claude](https://img.shields.io/badge/Claude_3.5_Sonnet-Model-7c3aed?style=for-the-badge)](https://www.anthropic.com/claude)
[![Docker](https://img.shields.io/badge/Docker-Sandbox-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![OpenTelemetry](https://img.shields.io/badge/OTEL%2BPrometheus%2BGrafana-Observability-3DBE29?style=for-the-badge)](https://opentelemetry.io/)

</div>

---

## ◈ What is APEX?

> **APEX** is a sophisticated, autonomous multi-agent system engineered for complex software engineering tasks. Unlike simple code generators, APEX employs a tiered, self-correcting **DAG (Directed Acyclic Graph)** architecture — analyzing, architecting, implementing, reviewing, testing, and optimizing code inside a secure sandboxed environment.

**Not just code generation. A full autonomous SDLC engine.**

---

## ◈ System Architecture

APEX leverages **[LangGraph](https://github.com/langchain-ai/langgraph)** for advanced state management and conditional routing — making the coding process a recursive, self-healing workflow rather than a linear pipeline.

```mermaid
graph TD
    User([User Request]) --> Orch[Orchestrator Agent]
    Orch --> |Decompose| Tier1{Tier 1: Parallel Research}

    subgraph Tier_1 [Requirements & Design]
        Tier1 --> Analyst[Analyst Agent]
        Tier1 --> Architect[Architect Agent]
    end

    Analyst & Architect --> CodeGen[CodeGen Agent]

    subgraph Tier_2 [Implementation]
        CodeGen --> Reviewer[Reviewer Agent]
    end

    Reviewer --> |Score < 7| CodeGen
    Reviewer --> |Score >= 7| Tester[Tester Agent]

    subgraph Tier_3 [Verification & Repair]
        Tester --> |Fail| Debugger[Debugger Agent]
        Debugger --> |Loop ≤ 3| Tester
        Tester --> |Pass| Optimizer[Optimizer Agent]
        Debugger --> |Exhausted| FH[Failure Handler]
    end

    Optimizer & FH --> Finalize([Final Artifact Delivery])

    style User fill:#f9f,stroke:#333,stroke-width:2px
    style Finalize fill:#00ff00,stroke:#333,stroke-width:2px
    style Orch fill:#66b2ff,stroke:#333
    style Debugger fill:#ff9999,stroke:#333
```

---

## ◈ 9 Specialist Agents

<div align="center">

| Agent | Core Responsibility | Technical Edge |
| :---: | :--- | :--- |
| 🎯 **Orchestrator** | Task decomposition & Routing | Dynamic DAG generation via LangGraph |
| 🔍 **Analyst** | Requirements Engineering | Semantic extraction of constraints & edge cases |
| 🏛️ **Architect** | System Design | Hierarchical file mapping & API contract design |
| ⚙️ **CodeGen** | Production Implementation | Context-aware generation with debug-patch merging |
| ✅ **Reviewer** | Quality Assurance | Hybrid AST (Ruff) metrics + LLM semantic scoring |
| 🧪 **Tester** | Verification | Automated Pytest generation & Sandbox execution |
| 🛠️ **Debugger** | Autonomous Repair | Traceback analysis & root-cause surgical patching |
| ⚡ **Optimizer** | Performance Engineering | Complexity analysis & hotspot optimization |
| 🛡️ **Failure Handler** | Graceful Degradation | Dead-letter queue & partial artifact recovery |

</div>

---

## ◈ Secure Execution & Analysis

APEX enforces a **multi-layered security and reliability strategy** at every stage:

<div align="center">

| Layer | Mechanism | Coverage |
|:---:|:---|:---|
| 🔒 **Subprocess Sandbox** | Memory caps, CPU quotas, `psutil` process tree cleanup | Local high-speed execution |
| 🐳 **Docker Isolation** | Disabled networking, read-only filesystem | High-risk isolated operations |
| 🔬 **AST Metrics** | Cyclomatic Complexity · Type Hint Coverage · Nesting Depth · Docstring Parity | Structural code analysis |

</div>

---

## ◈ Observability & Telemetry

Production-grade monitoring baked into the core — full visibility into agent reasoning and system performance.

```
📡  Distributed Tracing   →  OpenTelemetry + Jaeger    (full agentic flow visualization)
📊  Real-time Metrics     →  Prometheus exporters       (token usage, latency, quality scores)
📋  Structured Logging    →  structlog JSON             (ELK / Splunk ready)
📺  Dashboards            →  Grafana Mission Control    (pre-configured, zero-config)
```

**Monitoring Endpoints (after `docker compose up`):**

| Service | URL | Notes |
|:---:|:---:|:---|
| 🚀 FastAPI Docs | `http://localhost:8000/docs` | Interactive API explorer |
| 📊 Grafana | `http://localhost:3000` | `admin` / `apex-admin` |
| 📡 Prometheus | `http://localhost:9090` | Raw metrics |
| 🔭 Jaeger | `http://localhost:16686` | Distributed traces |

---

## ◈ Tech Stack

<div align="center">

### ⟡ Core Framework
[![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-FF6B35?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

### ⟡ AI / LLM
[![Anthropic](https://img.shields.io/badge/Claude_3.5_Sonnet-7c3aed?style=for-the-badge)](https://www.anthropic.com/claude)
[![OpenAI](https://img.shields.io/badge/OpenAI_Compatible-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)

### ⟡ Infrastructure & Sandbox
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)

### ⟡ Observability
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-000000?style=for-the-badge&logo=opentelemetry&logoColor=white)](https://opentelemetry.io/)
[![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white)](https://grafana.com/)
[![Jaeger](https://img.shields.io/badge/Jaeger_Tracing-66CFE3?style=for-the-badge)](https://www.jaegertracing.io/)

### ⟡ Code Quality
[![Ruff](https://img.shields.io/badge/Ruff-AST_Linter-D7FF64?style=for-the-badge)](https://docs.astral.sh/ruff/)
[![structlog](https://img.shields.io/badge/structlog-JSON_Logging-4B8BBE?style=for-the-badge)](https://www.structlog.org/)

</div>

---

## ◈ Getting Started

### Prerequisites

```
✦  Python 3.10+
✦  Docker & Docker Compose
✦  Redis (state persistence)
✦  Anthropic API Key
```

### Installation

```bash
# Clone the repository
git clone https://github.com/Gypsianmonk/Apex_coding_agent.git
cd Apex_coding_agent

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Set your API key (required)
# ANTHROPIC_API_KEY=sk-ant-...
```

### Run

```bash
# Option A — Local Development
python main.py

# Option B — Full Production Stack (Recommended)
docker compose up -d
```

---

## ◈ API Integration

### REST — Synchronous

```bash
curl -X POST http://localhost:8000/api/v1/code \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${APEX_API_KEY}" \
  -d '{
    "request": "Implement a thread-safe Singleton pattern in Python with unit tests",
    "stream": false
  }'
```

### WebSocket — Real-Time Streaming

Perfect for IDE plugins or interactive frontends.

```javascript
const socket = new WebSocket('ws://localhost:8000/ws/code');

socket.onopen = () => {
  socket.send(JSON.stringify({
    request: "Create a data processing pipeline with Pydantic"
  }));
};

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.agent}] ${data.message}`);
};
```

---

## ◈ License

This project is licensed under the **[MIT License](LICENSE)** — use it freely.

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:24243e,50:302b63,100:0f0c29&height=120&section=footer" width="100%"/>

*"9 agents. One mission. Ship production-grade code — autonomously."*

**Built with ❤️ by [GypsianMonk](https://github.com/GypsianMonk)**

</div>
