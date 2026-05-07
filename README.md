# 🚀 APEX: Production-Grade Multi-Agent AI Coding System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Claude 3.5 Sonnet](https://img.shields.io/badge/Model-Claude%203.5%20Sonnet-purple.svg)](https://www.anthropic.com/claude)
[![Docker](https://img.shields.io/badge/Sandbox-Docker-blue.svg)](https://www.docker.com/)
[![Observability](https://img.shields.io/badge/Observability-OTEL%2BPrometheus%2BGrafana-green.svg)](https://opentelemetry.io/)

**APEX** is a sophisticated, autonomous multi-agent system designed to handle complex software engineering tasks. Unlike simple code generators, APEX employs a tiered, self-correcting DAG (Directed Acyclic Graph) architecture to analyze, architect, implement, review, test, and optimize code in a secure, sandboxed environment.

---

## 🏛️ System Architecture

APEX leverages **LangGraph** for advanced state management and conditional routing, ensuring that the coding process is not just a linear pipeline, but a recursive, self-healing workflow.

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

## 🛠️ Specialist Agents

APEX consists of **9 autonomous agents**, each specialized in a specific phase of the software development lifecycle (SDLC).

| Agent | Core Responsibility | Technical Edge |
| :--- | :--- | :--- |
| **Orchestrator** | Task decomposition & Routing | Dynamic DAG generation via LangGraph |
| **Analyst** | Requirements Engineering | Semantic extraction of constraints & edge cases |
| **Architect** | System Design | Hierarchical file mapping & API contract design |
| **CodeGen** | Production Implementation | Context-aware generation with debug-patch merging |
| **Reviewer** | Quality Assurance | Hybrid AST (Ruff) metrics + LLM semantic scoring |
| **Tester** | Verification | Automated Pytest generation & Sandbox execution |
| **Debugger** | Autonomous Repair | Traceback analysis & root-cause surgical patching |
| **Optimizer** | Performance Engineering | Complexity analysis & hotspot optimization |
| **Failure Handler** | Graceful Degradation | Dead-letter queue & partial artifact recovery |

---

## 🔐 Secure Execution & Analysis

APEX prioritizes security and reliability through a multi-layered verification strategy:

- **Subprocess Sandbox**: High-speed local execution with strict memory caps, CPU quotas, and `psutil`-based process tree cleanup.
- **Docker Isolation**: (Optional) Fully isolated environments with disabled networking and read-only filesystems for high-risk operations.
- **AST Metrics**: Structural analysis including:
    - **Cyclomatic Complexity**: Ensuring maintainability.
    - **Type Hint Coverage**: Enforcing modern Python standards.
    - **Nesting Depth**: Preventing "spaghetti" logic.
    - **Docstring Analysis**: Ensuring documentation parity.

---

## 📊 Observability & Telemetry

Production-grade monitoring is baked into the core, providing deep visibility into agent reasoning and system performance.

- **Distributed Tracing**: Full OpenTelemetry integration with **Jaeger** for visualizing the entire agentic flow.
- **Real-time Metrics**: **Prometheus** exporters for:
    - Token consumption & LLM latency.
    - Agent success/failure rates.
    - Sandbox execution duration.
    - Code quality scores over time.
- **Structured Logging**: `structlog`-based JSON logs for effortless ELK/Splunk integration.
- **Monitoring Stack**: Pre-configured **Grafana** dashboards for a "Mission Control" experience.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Docker & Docker Compose (for full stack)
- Redis (for state persistence)
- Anthropic API Key

### Installation
```bash
# Clone the repository
git clone https://github.com/Gypsianmonk/Apex_coding_agent.git
cd Apex_coding_agent

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration
Create a `.env` file from the template:
```bash
cp .env.example .env
# Essential: set your ANTHROPIC_API_KEY
```

### Execution
**Option A: Local Development**
```bash
python main.py
```

**Option B: Production Stack (Recommended)**
```bash
docker compose up -d
```
*Access Services:*
- **FastAPI UI**: `http://localhost:8000/docs`
- **Grafana**: `http://localhost:3000` (Default: admin / apex-admin)
- **Prometheus**: `http://localhost:9090`
- **Jaeger**: `http://localhost:16686`

---

## 🔌 API Integration

### REST Interface (Synchronous)
```bash
curl -X POST http://localhost:8000/api/v1/code \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${APEX_API_KEY}" \
  -d '{
    "request": "Implement a thread-safe Singleton pattern in Python with unit tests",
    "stream": false
  }'
```

### WebSocket Interface (Real-Time Streaming)
Perfect for building IDE plugins or interactive UIs.
```javascript
const socket = new WebSocket('ws://localhost:8000/ws/code');

socket.onopen = () => {
  socket.send(JSON.stringify({ request: "Create a data processing pipeline with Pydantic" }));
};

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.agent}] ${data.message}`);
};
```

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---
<p align="center">
  Built with ❤️ by the APEX Engineering Team
</p>
