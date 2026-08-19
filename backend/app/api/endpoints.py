import asyncio
import logging
import os
import time

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent_progress import close_queue, get_queue, push_event, push_sentinel
from app.config import settings
from app.services.adk_agents import DataJanitorAgent, HypothesisBotAgent, InsightOrchestraWorkflow
from app.services.explain_agent import ExplainabilityAgent
from app.services.nlq_agent import NaturalLanguageQueryAgent
from app.services.report_agent import ReportGeneratorAgent
from app.services.session_manager import get_session_manager
from app.services.summarizer_agent import InsightSummarizerAgent
from app.utils.file_utils import UPLOAD_DIR, save_upload_file
from app.utils.json_sanitize import sanitize_json

logger = logging.getLogger(__name__)

DEMO_MODE = settings.demo_mode

router = APIRouter()

# Session manager (Redis-backed with in-memory fallback)
_session_manager = get_session_manager()


class ProcessRequest(BaseModel):
    file_path: str
    session_id: str | None = None


class NLQRequest(BaseModel):
    file_path: str
    question: str
    session_id: str | None = None


class BigQueryRequest(BaseModel):
    credentials_json: str  # JSON string of service account credentials
    query: str


def get_df(file_path: str) -> pd.DataFrame:
    """Load DataFrame from file path."""
    # Security: Resolve and validate the path against allowed directories
    # before touching the filesystem, to prevent path traversal. Paths
    # outside the sandbox are reported as "not found" (rather than a
    # distinct "access denied") so we don't confirm the existence of
    # files outside it.
    real_path = os.path.realpath(file_path)
    allowed_dirs = ["/tmp", UPLOAD_DIR]
    in_allowed_dir = any(
        real_path == allowed_dir or real_path.startswith(allowed_dir + os.sep)
        for allowed_dir in allowed_dirs
    )
    if not in_allowed_dir or not os.path.isfile(real_path):
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        return pd.read_csv(real_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {e}") from e


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload CSV file."""
    try:
        file_path = save_upload_file(file)
        return {"file_path": file_path}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="File upload failed.") from e


@router.post("/process")
async def process_data(request: ProcessRequest):
    """Run full Insight Orchestra workflow with real-time agent progress events."""
    df = get_df(request.file_path)
    workflow = InsightOrchestraWorkflow()
    sid = request.session_id

    try:
        push_event(sid, agent_id="janitor", status="running")
        t0 = time.monotonic()
        cleaner_result = await asyncio.to_thread(workflow.cleaner.run, df.to_dict(orient="records"))
        cleaned_data = cleaner_result["cleaned_data"]
        r = cleaner_result["report"]
        push_event(
            sid,
            agent_id="janitor",
            status="done",
            output=f"Removed {r.get('duplicates_removed', 0)} dupes, "
            f"handled {r.get('total_missing', 0)} missing values.",
            duration=int((time.monotonic() - t0) * 1000),
        )

        push_event(sid, agent_id="hypothesis", status="running")
        t0 = time.monotonic()
        hypothesis_result = await asyncio.to_thread(workflow.hypothesis.run, cleaned_data)
        hypotheses = hypothesis_result["hypotheses"]
        stats_summary = HypothesisBotAgent._build_stats_summary(pd.DataFrame(cleaned_data))
        push_event(
            sid,
            agent_id="hypothesis",
            status="done",
            output=f"Found {len(hypotheses)} insights.",
            duration=int((time.monotonic() - t0) * 1000),
        )

        push_event(sid, agent_id="debate", status="running")
        t0 = time.monotonic()
        debate_result = await asyncio.to_thread(workflow.debate.run, hypotheses, stats_summary)
        consensus = debate_result["summary"].get("consensus")
        top = consensus.get("hypothesis", "")[:80] if consensus else "—"
        push_event(
            sid,
            agent_id="debate",
            status="done",
            output=f"Top insight: {top}…" if len(top) == 80 else f"Top insight: {top}",
            duration=int((time.monotonic() - t0) * 1000),
        )

        push_event(sid, agent_id="viz", status="running")
        t0 = time.monotonic()
        viz_result = await asyncio.to_thread(
            workflow.viz.run, cleaned_data, consensus, hypotheses=hypotheses
        )
        num_plots = len(viz_result.get("chart_info", {}).get("plots", []))
        push_event(
            sid,
            agent_id="viz",
            status="done",
            output=f"Generated {num_plots} chart(s).",
            duration=int((time.monotonic() - t0) * 1000),
        )

        # Generate narrative summary + suggested questions
        workflow_results = {
            "cleaner": cleaner_result,
            "hypothesis": hypothesis_result,
            "debate": debate_result,
            "viz": viz_result,
            "stats": stats_summary,
        }
        summarizer = InsightSummarizerAgent(llm_service=workflow.llm)
        summary_result = await asyncio.to_thread(summarizer.run, workflow_results)
    finally:
        # Always close the progress stream, even if an agent raised.
        push_sentinel(sid)

    # Store analysis context in session so NLQ queries can reference it.
    # Charts are kept so server-side exports can embed them; they are stripped
    # before the history is used as LLM context (see /nlq).
    if sid:
        _session_manager.append(
            sid,
            {
                "role": "analysis",
                "narrative": summary_result.get("narrative", ""),
                "top_insight": consensus.get("hypothesis", "") if consensus else "",
                "hypotheses": hypotheses[:5],
                "charts": [
                    {"title": p.get("title", ""), "plotly_json": p.get("plotly_json")}
                    for p in (viz_result.get("chart_info") or {}).get("plots", [])
                    if p.get("plotly_json")
                ],
            },
        )

    # Small sample of the cleaned data so the UI can show a preview table.
    import json as _json

    preview_df = pd.DataFrame(cleaned_data)
    preview = {
        "columns": preview_df.columns.tolist(),
        "rows": _json.loads(preview_df.head(20).to_json(orient="records")),
    }

    return sanitize_json(
        {
            "cleaner": cleaner_result,
            "hypothesis": hypothesis_result,
            "debate": debate_result,
            "viz": viz_result,
            "narrative": summary_result.get("narrative", ""),
            "suggested_questions": summary_result.get("suggested_questions", []),
            "preview": preview,
        }
    )


@router.post("/nlq")
async def natural_language_query(request: NLQRequest):
    """Natural language query with LLM-powered code generation."""
    sid = request.session_id
    df = get_df(request.file_path)

    try:
        # --- Phase 1: Data Janitor ---
        push_event(sid, agent_id="janitor", status="running")
        t0 = time.monotonic()
        janitor = DataJanitorAgent(name="nlq_cleaner")
        cleaned_result = await asyncio.to_thread(janitor.run, df.to_dict(orient="records"))
        df = pd.DataFrame(cleaned_result["cleaned_data"])
        report = cleaned_result["report"]
        janitor_summary = (
            f"Removed {report.get('duplicates_removed', 0)} duplicates, "
            f"imputed {report.get('total_missing', 0)} missing values."
        )
        push_event(
            sid,
            agent_id="janitor",
            status="done",
            output=janitor_summary,
            duration=int((time.monotonic() - t0) * 1000),
        )

        # Get session context if provided. Chart payloads are stored in the
        # history for exports but are far too large for an LLM prompt — strip
        # them before passing the history as context.
        context = None
        if sid:
            context = [
                {k: v for k, v in entry.items() if k not in ("plot_json", "charts")}
                for entry in (_session_manager.get(sid) or [])
            ]

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
                sid,
                agent_id="viz",
                status="done",
                output="Chart generated successfully.",
                duration=0,
            )
    finally:
        # Always close the progress stream, even if an agent raised.
        push_sentinel(sid)

    # Store in session (plot_json included so server-side exports can embed
    # the chart; it is stripped from LLM context above).
    if sid:
        interaction = {
            "question": request.question,
            "answer": response.answer,
            "code": response.code,
        }
        if response.plot_json:
            interaction["plot_json"] = response.plot_json
        _session_manager.append(sid, interaction)

    return sanitize_json(
        {
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
    )


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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # Other errors (BigQuery API errors, etc.)
        raise HTTPException(status_code=500, detail=f"BigQuery error: {str(e)}") from e


class ConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None


@router.get("/config")
async def get_config():
    """Current LLM provider/model and what's switchable."""
    from app import runtime_config

    keymap = {
        "openai": bool(settings.openai_api_key and "your-" not in settings.openai_api_key),
        "anthropic": bool(
            settings.anthropic_api_key and settings.anthropic_api_key != "sk-ant-..."
        ),
        "deepseek": bool(settings.deepseek_api_key and settings.deepseek_api_key != "sk-..."),
        "ollama": True,
    }
    return {
        **runtime_config.current(),
        "available": runtime_config.PROVIDERS,
        "ready": keymap,
    }


@router.post("/config")
async def update_config(update: ConfigUpdate):
    """Switch provider/model at runtime (no restart needed)."""
    from app import runtime_config

    if update.provider and update.provider not in runtime_config.PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{update.provider}'.")
    prov = update.provider or runtime_config.get_provider()
    keymap = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "deepseek": settings.deepseek_api_key,
    }
    if prov in keymap and (
        not keymap[prov] or keymap[prov] in ("sk-...", "sk-ant-...", "your-openai-api-key-here")
    ):
        raise HTTPException(
            status_code=400, detail=f"No API key configured for '{prov}' on the server."
        )
    runtime_config.set_override(update.provider, update.model)
    return runtime_config.current()


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
        raise HTTPException(status_code=400, detail=f"Failed to load dataset: {str(e)}") from e


@router.get("/agents/stream/{session_id}")
async def stream_agent_logs(session_id: str):
    """
    Stream real agent progress events for the UI.

    The queue is registered here (before the /nlq or /process call fires)
    so no events are dropped.  Producers call push_event() and always emit a
    None sentinel (even on error) so we close promptly; a heartbeat keeps the
    connection alive through long CPU inference where no events flow, and an
    overall cap guards against a producer that dies without a sentinel.
    """
    import json

    queue = get_queue(session_id)
    # Bound total stream life to the LLM timeout plus margin so a crashed
    # producer can't leak the connection indefinitely.
    deadline = time.monotonic() + settings.request_timeout + 30

    async def event_generator():
        try:
            while True:
                if time.monotonic() >= deadline:
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    # No events yet — keep the connection alive and keep waiting.
                    yield {"event": "ping", "data": "{}"}
                    continue

                if event is None:  # sentinel: pipeline finished (or errored)
                    break

                yield {"data": json.dumps(event)}
        finally:
            close_queue(session_id)

    return EventSourceResponse(event_generator())
