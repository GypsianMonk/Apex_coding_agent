"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Main API Server
 FastAPI + WebSocket streaming + REST endpoints.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

import structlog
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from core.config import get_settings
from core.state import ApexState
from core.graph import compile_graph
from monitoring.telemetry import init_telemetry, ACTIVE_SESSIONS
from tools.cache import get_cache

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Lifespan — Startup / Shutdown
# ═══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize telemetry, cache, and compile graph on startup."""
    init_telemetry()
    logger.info("apex.startup", version="1.0.0")

    # Compile the LangGraph
    app.state.graph = compile_graph()
    logger.info("apex.graph.compiled")

    # Connect to Redis (non-fatal if unavailable)
    try:
        app.state.cache = await get_cache()
        logger.info("apex.redis.connected")
    except Exception as exc:
        logger.warning("apex.redis.unavailable", error=str(exc))
        app.state.cache = None

    # Store active sessions
    app.state.sessions: dict[str, ApexState] = {}

    yield

    # Shutdown
    if app.state.cache:
        try:
            await app.state.cache.disconnect()
        except Exception:
            pass
    logger.info("apex.shutdown")


# ═══════════════════════════════════════════════════════════════
#  App Configuration
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="APEX Coding Agent",
    description="Production-grade multi-agent AI coding system with DAG orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════
#  Auth Dependency
# ═══════════════════════════════════════════════════════════════

async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    settings = get_settings()
    if settings.apex_api_key and x_api_key != settings.apex_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key or "anonymous"


# ═══════════════════════════════════════════════════════════════
#  Request / Response Models
# ═══════════════════════════════════════════════════════════════

class CodingRequest(BaseModel):
    request: str = Field(..., min_length=5, description="What you want APEX to build")
    project_context: dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None


class CodingResponse(BaseModel):
    session_id: str
    status: str
    summary: str
    files: list[dict[str, Any]]
    review: dict[str, Any]
    tests: dict[str, Any]
    metrics: dict[str, Any]


class SessionStatus(BaseModel):
    session_id: str
    status: str
    current_agent: str
    progress: float
    trace: list[dict[str, Any]]


# ═══════════════════════════════════════════════════════════════
#  REST Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0", "service": "apex-coding-agent"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/code", response_model=CodingResponse)
async def generate_code(
    req: CodingRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    Submit a coding task. Runs the full APEX pipeline synchronously.
    For real-time progress, use the WebSocket endpoint instead.
    """
    session_id = req.session_id or str(uuid.uuid4())
    ACTIVE_SESSIONS.inc()

    try:
        logger.info("api.code.start", session_id=session_id, request_length=len(req.request))

        # Initialize state
        state = ApexState(
            session_id=session_id,
            user_request=req.request,
            project_context=req.project_context,
        )

        # Store in active sessions
        app.state.sessions[session_id] = state

        # Run the graph
        initial_state = state.model_dump(mode="json")
        result = await app.state.graph.ainvoke(initial_state)

        # Parse final state
        final_state = ApexState.model_validate(result)
        output = final_state.final_output or {}

        logger.info("api.code.complete", session_id=session_id, summary=final_state.summary)

        return CodingResponse(
            session_id=session_id,
            status=output.get("status", "completed"),
            summary=final_state.summary,
            files=output.get("files", []),
            review=output.get("review", {}),
            tests=output.get("tests", {}),
            metrics=output.get("metrics", {}),
        )

    except Exception as exc:
        logger.error("api.code.error", session_id=session_id, error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(exc)}")
    finally:
        ACTIVE_SESSIONS.dec()
        app.state.sessions.pop(session_id, None)


@app.get("/api/v1/sessions/{session_id}", response_model=SessionStatus)
async def get_session_status(session_id: str, api_key: str = Depends(verify_api_key)):
    """Get the current status of a running session."""
    state = app.state.sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    total_agents = max(len(state.subtasks), 1)
    completed = sum(1 for st in state.subtasks if st.status.value == "completed")

    return SessionStatus(
        session_id=session_id,
        status=state.status.value,
        current_agent=state.current_agent.value,
        progress=round(completed / total_agents, 2),
        trace=state.agent_trace,
    )


# ═══════════════════════════════════════════════════════════════
#  WebSocket — Real-Time Streaming
# ═══════════════════════════════════════════════════════════════

@app.websocket("/ws/code")
async def websocket_code(ws: WebSocket):
    """
    WebSocket endpoint for real-time coding sessions.

    Protocol:
    1. Client sends: {"request": "Build a REST API...", "project_context": {}}
    2. Server streams: {"event": "agent_start|agent_complete|progress|error|done", ...}
    3. Final message: {"event": "done", "result": {...}}
    """
    await ws.accept()
    session_id = str(uuid.uuid4())
    ACTIVE_SESSIONS.inc()

    try:
        # Receive the coding request
        data = await ws.receive_json()
        request_text = data.get("request", "")
        project_context = data.get("project_context", {})

        if not request_text:
            await ws.send_json({"event": "error", "message": "Empty request"})
            return

        logger.info("ws.session.start", session_id=session_id)
        await ws.send_json({
            "event": "session_start",
            "session_id": session_id,
            "message": "APEX pipeline starting...",
        })

        # Initialize state
        state = ApexState(
            session_id=session_id,
            user_request=request_text,
            project_context=project_context,
        )
        app.state.sessions[session_id] = state

        # Run graph with streaming updates
        initial_state = state.model_dump(mode="json")
        result = await _run_graph_with_streaming(
            app.state.graph, initial_state, ws, session_id
        )

        # Send final result
        final_state = ApexState.model_validate(result)
        output = final_state.final_output or {}

        await ws.send_json({
            "event": "done",
            "session_id": session_id,
            "result": output,
            "summary": final_state.summary,
        })

    except WebSocketDisconnect:
        logger.info("ws.disconnected", session_id=session_id)
    except Exception as exc:
        logger.error("ws.error", session_id=session_id, error=str(exc))
        try:
            await ws.send_json({"event": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        ACTIVE_SESSIONS.dec()
        app.state.sessions.pop(session_id, None)


async def _run_graph_with_streaming(
    graph, initial_state: dict, ws: WebSocket, session_id: str
) -> dict:
    """Run the graph and stream agent progress events via WebSocket."""
    last_agent = None
    result = initial_state

    async for event in graph.astream(initial_state):
        for node_name, node_output in event.items():
            result = node_output

            # Send agent progress
            if node_name != last_agent:
                if last_agent:
                    await ws.send_json({
                        "event": "agent_complete",
                        "agent": last_agent,
                        "session_id": session_id,
                    })

                await ws.send_json({
                    "event": "agent_start",
                    "agent": node_name,
                    "session_id": session_id,
                    "message": f"Running {node_name}...",
                })
                last_agent = node_name

    if last_agent:
        await ws.send_json({
            "event": "agent_complete",
            "agent": last_agent,
            "session_id": session_id,
        })

    return result


# ═══════════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.apex_host,
        port=settings.apex_port,
        workers=1,  # Use 1 for dev, settings.apex_workers for prod
        reload=True,
        log_level=settings.log_level.lower(),
    )
