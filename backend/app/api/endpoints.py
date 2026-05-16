from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import pandas as pd
import asyncio
import time
from sse_starlette.sse import EventSourceResponse
from app.utils.file_utils import save_upload_file, UPLOAD_DIR
from app.services.adk_agents import InsightOrchestraWorkflow, DataJanitorAgent
from app.services.nlq_agent import NaturalLanguageQueryAgent
from app.services.summarizer_agent import InsightSummarizerAgent
from app.services.explain_agent import ExplainabilityAgent
from app.services.report_agent import ReportGeneratorAgent
from app.services.llm_service import LLMService
from app.services.sandbox_executor import SandboxExecutor
from app.agent_progress import get_queue, close_queue, push_event, push_sentinel
import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)

DEMO_MODE = settings.demo_mode

router = APIRouter()

# Session manager (Redis-backed with in-memory fallback)
from app.services.session_manager import get_session_manager

_session_manager = get_session_manager()

class ProcessRequest(BaseModel):
    file_path: str


class NLQRequest(BaseModel):
    file_path: str
    question: str
    session_id: Optional[str] = None


class BigQueryRequest(BaseModel):
    credentials_json: str  # JSON string of service account credentials
    query: str


def get_df(file_path: str) -> pd.DataFrame:
    """Load DataFrame from file path."""
    # Security: Validate file path to prevent path traversal
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    # Ensure the file is within allowed directories (absolute paths only)
    allowed_dirs = ["/tmp", UPLOAD_DIR]
    real_path = os.path.realpath(file_path)
    if not any(real_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
        raise HTTPException(
            status_code=403, detail="Access denied: file outside allowed directories."
        )

    try:
        return pd.read_csv(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {e}")


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload CSV file."""
    try:
        file_path = save_upload_file(file)
        return {"file_path": file_path}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="File upload failed.")


@router.post("/process")
async def process_data(request: ProcessRequest, session_id: Optional[str] = None):
    """Run full Insight Orchestra workflow with real-time agent progress events."""
    df = get_df(request.file_path)
    workflow = InsightOrchestraWorkflow()
    sid = session_id

    def _run_janitor():
        return workflow.cleaner.run(df.to_dict(orient="records"))

    push_event(sid, agent_id="janitor", status="running")
    t0 = time.monotonic()
    cleaner_result = await asyncio.to_thread(_run_janitor)
    cleaned_data = cleaner_result["cleaned_data"]
    r = cleaner_result["report"]
    push_event(sid, agent_id="janitor", status="done",
               output=f"Removed {r.get('duplicates_removed',0)} dupes, imputed {r.get('total_missing',0)} missing values.",
               duration=int((time.monotonic() - t0) * 1000))

    push_event(sid, agent_id="hypothesis", status="running")
    t0 = time.monotonic()
    hypothesis_result = await asyncio.to_thread(workflow.hypothesis.run, cleaned_data)
    hypotheses = hypothesis_result["hypotheses"]
    push_event(sid, agent_id="hypothesis", status="done",
               output=f"Generated {len(hypotheses)} hypotheses.",
               duration=int((time.monotonic() - t0) * 1000))

    push_event(sid, agent_id="debate", status="running")
    t0 = time.monotonic()
    debate_result = await asyncio.to_thread(workflow.debate.run, hypotheses)
    consensus = debate_result["summary"].get("consensus")
    push_event(sid, agent_id="debate", status="done",
               output="Top hypothesis scored. Consensus reached.",
               duration=int((time.monotonic() - t0) * 1000))

    push_event(sid, agent_id="viz", status="running")
    t0 = time.monotonic()
    viz_result = await asyncio.to_thread(
        workflow.viz.run, cleaned_data, consensus, hypotheses=hypotheses
    )
    num_plots = len(viz_result.get("chart_info", {}).get("plots", []))
    push_event(sid, agent_id="viz", status="done",
               output=f"Generated {num_plots} chart(s).",
               duration=int((time.monotonic() - t0) * 1000))

    push_sentinel(sid)

    return {
        "cleaner":    cleaner_result,
        "hypothesis": hypothesis_result,
        "debate":     debate_result,
        "viz":        viz_result,
    }


@router.post("/nlq")
async def natural_language_query(request: NLQRequest):
    """Natural language query with LLM-powered code generation."""
    sid = request.session_id
    df = get_df(request.file_path)

    # --- Phase 1: Data Janitor ---
    push_event(sid, agent_id="janitor", status="running")
    t0 = time.monotonic()
    janitor = DataJanitorAgent(name="nlq_cleaner")
    cleaned_result = await asyncio.to_thread(
        janitor.run, df.to_dict(orient="records")
    )
    df = pd.DataFrame(cleaned_result["cleaned_data"])
    report = cleaned_result["report"]
    janitor_summary = (
        f"Removed {report.get('duplicates_removed', 0)} duplicates, "
        f"imputed {report.get('total_missing', 0)} missing values."
    )
    push_event(
        sid, agent_id="janitor", status="done",
        output=janitor_summary,
        duration=int((time.monotonic() - t0) * 1000),
    )

    # Get session context if provided
    context = None
    if sid:
        context = _session_manager.get(sid)

    # --- Phase 2: NLQ Agent ---
    push_event(sid, agent_id="nlq", status="running")
    t0 = time.monotonic()
    agent = NaturalLanguageQueryAgent()
    response = await asyncio.to_thread(agent.run, df, request.question, context, sid)
    if response.execution_success:
        push_event(
            sid,
            agent_id="nlq",
            status="done",
            output="Generated and executed query successfully.",
            duration=int((time.monotonic() - t0) * 1000),
        )
    else:
        push_event(
            sid,
            agent_id="nlq",
            status="error",
            output=response.error or "Query execution failed.",
            duration=int((time.monotonic() - t0) * 1000),
        )

    # --- Phase 3: Viz Whiz (emit only when a plot was produced) ---
    if response.plot_json:
        push_event(sid, agent_id="viz", status="running")
        push_event(
            sid, agent_id="viz", status="done",
            output="Chart generated successfully.",
            duration=0,
        )

    # Signal end-of-stream
    push_sentinel(sid)

    # Store in session
    if sid:
        _session_manager.append(
            sid,
            {
                "question": request.question,
                "answer": response.answer,
                "code": response.code,
            },
        )

    return {
        "answer": response.answer,
        "code": response.code,
        "reasoning": response.reasoning,
        "plot_json": response.plot_json,
        "needs_clarification": response.needs_clarification,
        "clarification_question": response.clarification_question,
        "execution_success": response.execution_success,
        "error": response.error,
        "session_id": sid,
    }


@router.post("/summarize")
async def summarize_insights(payload: dict):
    """Summarize workflow results."""
    workflow_results = payload.get("workflow_results", {})

    # Validate input is a dictionary
    if not isinstance(workflow_results, dict):
        raise HTTPException(status_code=400, detail="workflow_results must be a dictionary")

    agent = InsightSummarizerAgent()
    return agent.run(workflow_results)


@router.post("/explain")
async def explain_plot(payload: dict):
    """Explain a visualization."""
    plot = payload.get("plot", {})

    # Validate input is a dictionary
    if not isinstance(plot, dict):
        raise HTTPException(status_code=400, detail="plot must be a dictionary")

    agent = ExplainabilityAgent()
    return agent.run(plot)


@router.post("/report")
async def generate_report(payload: dict):
    """Generate HTML report."""
    workflow_results = payload.get("workflow_results", {})

    # Validate input is a dictionary
    if not isinstance(workflow_results, dict):
        raise HTTPException(status_code=400, detail="workflow_results must be a dictionary")

    agent = ReportGeneratorAgent()
    return agent.run(workflow_results)


@router.post("/bigquery")
async def bigquery_fetch(request: BigQueryRequest):
    """Fetch data from BigQuery."""
    from app.utils.bigquery_utils import run_bigquery_query

    try:
        df = run_bigquery_query(request.credentials_json, request.query)
        temp_path = f"/tmp/bq_{os.urandom(8).hex()}.csv"
        df.to_csv(temp_path, index=False)
        return {"file_path": temp_path, "columns": df.columns.tolist(), "row_count": len(df)}
    except ValueError as e:
        # Validation errors - return 400
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Other errors (BigQuery API errors, etc.)
        raise HTTPException(status_code=500, detail=f"BigQuery error: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session context."""
    return {"session_id": session_id, "history": _session_manager.get(session_id)}


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear session context."""
    _session_manager.delete(session_id)
    return {"status": "cleared"}


@router.get("/demo/list")
async def list_demo_datasets():
    """List all available demo datasets."""
    if not DEMO_MODE:
        raise HTTPException(status_code=404, detail="Demo endpoint disabled in production")

    from app.utils.demo_data import DEMO_DATASETS

    datasets = {}
    for key, config in DEMO_DATASETS.items():
        datasets[key] = {
            "id": key,
            "name": config["name"],
            "description": config["description"],
            "rows": config["rows"],
            "columns": config["columns"],
            "use_cases": config["use_cases"],
        }

    return {"datasets": datasets}


@router.get("/demo/load")
async def load_demo_data(dataset_id: str = "sales"):
    """Load a demo dataset by ID."""
    if not DEMO_MODE:
        raise HTTPException(status_code=404, detail="Demo endpoint disabled in production")

    from app.utils.demo_data import get_demo_dataset

    try:
        df, metadata = get_demo_dataset(dataset_id)
        temp_path = f"/tmp/demo_{dataset_id}_{os.urandom(8).hex()}.csv"
        df.to_csv(temp_path, index=False)

        return {
            "file_path": temp_path,
            "dataset_id": metadata["dataset_id"],
            "dataset_name": metadata["name"],
            "columns": metadata["column_names"],
            "row_count": metadata["rows"],
            "column_count": metadata["columns"],
            "description": metadata["description"],
            "use_cases": metadata["use_cases"],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load dataset: {str(e)}")


@router.get("/agents/stream/{session_id}")
async def stream_agent_logs(session_id: str):
    """
    Stream real agent progress events for the UI.

    The queue is registered here (before the /nlq or /process call fires)
    so no events are dropped.  Producers call push_event(); we drain the
    queue until a None sentinel arrives or 60 s of silence passes.
    """
    import json
    queue = get_queue(session_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    # No events for 60 s — close gracefully
                    break

                if event is None:   # sentinel: pipeline finished
                    break

                yield {"data": json.dumps(event)}
        finally:
            close_queue(session_id)

    return EventSourceResponse(event_generator())
