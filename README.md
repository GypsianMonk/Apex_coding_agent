# 🚀 APEX Coding Agent

**Production-grade multi-agent AI coding system** — powered by Claude, orchestrated by LangGraph, served via FastAPI.

> No one matches this system.

---

## Architecture

```
User Request
     │
     ▼
┌─────────────────┐
│   Orchestrator   │  ← Decomposes task into DAG of subtasks
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────┐
│Analyst │ │ Architect │  ← Tier 1: PARALLEL
└───┬────┘ └────┬─────┘
    └─────┬─────┘
          ▼
   ┌──────────────┐
   │  Code Gen     │  ← Tier 2: Generates all files
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │   Reviewer    │  ← Tier 3: AST lint + LLM review
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │    Tester     │  ← Tier 3: Sandbox execution
   └──────┬───────┘
          │
     ┌────┴────┐
     │ PASS?   │
     └────┬────┘
    yes   │   no
     │    └──► ┌──────────┐
     │         │ Debugger  │ ← Tier 4: Surgical patches
     │         └─────┬────┘
     │               │ (loop back to Tester, max 3x)
     ▼               ▼
┌──────────┐   ┌──────────────┐
│Optimizer │   │Failure Handler│ ← Tier 5: Dead letter queue
└────┬─────┘   └──────┬───────┘
     └────┬───────────┘
          ▼
    ┌───────────┐
    │  FINALIZE  │ → Complete output with all files, tests, metrics
    └───────────┘
```

## Quick Start

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

### 3. Run
```bash
# Development
python main.py

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Docker (Full Stack)
```bash
docker compose up -d
```
This starts: API server, Redis, Prometheus, Grafana, Jaeger

## API Usage

### REST — Synchronous
```bash
curl -X POST http://localhost:8000/api/v1/code \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"request": "Build a FastAPI REST API for a todo app with SQLite"}'
```

### WebSocket — Real-Time Streaming
```python
import asyncio
import websockets
import json

async def run():
    async with websockets.connect("ws://localhost:8000/ws/code") as ws:
        await ws.send(json.dumps({
            "request": "Build a CLI calculator in Python"
        }))
        async for message in ws:
            event = json.loads(message)
            print(f"[{event['event']}] {event.get('message', '')}")
            if event["event"] == "done":
                break

asyncio.run(run())
```

## System Components

| Component | Purpose |
|-----------|---------|
| **LangGraph** | DAG-based orchestration with conditional routing |
| **Claude API** | Real LLM calls in every agent |
| **Subprocess Sandbox** | Secure code execution with timeout/memory limits |
| **Docker Sandbox** | Optional full isolation (network disabled, read-only FS) |
| **Ruff + AST** | Static analysis + structural code metrics |
| **Redis** | State snapshots, agent output cache, pub/sub progress |
| **Prometheus** | Counters, histograms, gauges for all operations |
| **Grafana** | Dashboards for monitoring |
| **Jaeger** | Distributed tracing via OpenTelemetry |

## Agent Capabilities

| Agent | What It Does |
|-------|-------------|
| Orchestrator | Decomposes tasks into DAG, assigns agents, routes |
| Analyst | Extracts requirements, constraints, edge cases, acceptance criteria |
| Architect | Designs file structure, data models, API contracts |
| CodeGen | Writes complete, production-ready code files |
| Reviewer | Hybrid AST + LLM review with quality scoring (1-10) |
| Tester | Generates pytest suites, executes in sandbox |
| Debugger | Diagnoses failures, produces surgical patches (max 3 loops) |
| Optimizer | Finds performance hotspots, applies optimizations |
| Failure Handler | Dead-letter queue, retry/escalate/partial result |

## Monitoring

- **Metrics**: `http://localhost:8000/metrics` (Prometheus format)
- **Grafana**: `http://localhost:3000` (admin/apex-admin)
- **Jaeger**: `http://localhost:16686` (distributed traces)

## License

MIT
