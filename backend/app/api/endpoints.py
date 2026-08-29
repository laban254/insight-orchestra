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
from app.services.dataset_cache import get_cleaned
from app.services.dataset_registry import (
    DATASET_DIR,
    DatasetMissingError,
    get_dataset_registry,
)
from app.services.explain_agent import ExplainabilityAgent
from app.services.nlq_agent import NaturalLanguageQueryAgent
from app.services.report_agent import ReportGeneratorAgent
from app.services.session_manager import get_session_manager
from app.services.summarizer_agent import InsightSummarizerAgent
from app.utils.dataset_io import describe_dataset, read_dataset, sample_for_analysis
from app.utils.file_utils import discard_upload, save_upload_file
from app.utils.json_sanitize import sanitize_json

logger = logging.getLogger(__name__)

DEMO_MODE = settings.demo_mode

router = APIRouter()

# Session manager (Redis-backed with in-memory fallback)
_session_manager = get_session_manager()
_datasets = get_dataset_registry()


class ProcessRequest(BaseModel):
    dataset_id: str
    session_id: str | None = None


class NLQRequest(BaseModel):
    dataset_id: str
    question: str
    session_id: str | None = None


class BigQueryRequest(BaseModel):
    credentials_json: str  # JSON string of service account credentials
    query: str


def resolve_dataset_path(dataset_id: str) -> str:
    """Path for a registered dataset, or a 404 written for the user.

    The client holds an opaque id, never a path, so there is no
    caller-supplied path to validate — the registry is the only thing that
    can name a file, and it only ever names files the server wrote.
    """
    try:
        return _datasets.resolve_path(dataset_id)
    except DatasetMissingError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


def read_frame(path: str) -> pd.DataFrame:
    try:
        return read_dataset(path).df
    except ValueError as e:
        # read_dataset raises ValueError with a user-facing message.
        raise HTTPException(status_code=400, detail=str(e)) from e


def get_df(dataset_id: str) -> pd.DataFrame:
    """Load the DataFrame for a registered dataset."""
    return read_frame(resolve_dataset_path(dataset_id))


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV, returning its shape, column types and a preview."""
    try:
        file_path = save_upload_file(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="File upload failed.") from e

    # Parse now rather than at analysis time. A file that can't be read is a
    # failed upload, and reporting it later — after the UI has said the
    # upload succeeded — is the worst version of that error.
    try:
        result = read_dataset(file_path)
    except ValueError as e:
        discard_upload(file_path)
        raise HTTPException(status_code=400, detail=str(e)) from e

    name = file.filename or "Uploaded file"
    dataset_id = _datasets.register(file_path, name=name, source="upload")

    return sanitize_json(
        {
            "dataset_id": dataset_id,
            "name": name,
            **describe_dataset(result.df),
            "assumptions": result.assumptions,
        }
    )


@router.post("/process")
async def process_data(request: ProcessRequest):
    """Run full Insight Orchestra workflow with real-time agent progress events."""
    path = resolve_dataset_path(request.dataset_id)
    workflow = InsightOrchestraWorkflow()
    sid = request.session_id

    try:
        push_event(sid, agent_id="janitor", status="running")
        t0 = time.monotonic()

        # Shares the cache with /nlq, so the first follow-up question after
        # an analysis doesn't re-read and re-clean the same file.
        def _clean():
            frame, notice = sample_for_analysis(read_frame(path))
            result = workflow.cleaner.run(frame)
            result["sampling"] = notice
            return result

        cleaned, _from_cache = await asyncio.to_thread(
            get_cleaned, request.dataset_id, path, _clean
        )
        cleaned_df = cleaned.df
        sampling = cleaned.sampling
        cleaner_result = {"cleaned_df": cleaned_df, "report": cleaned.report}
        r = cleaned.report
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
        hypothesis_result = await asyncio.to_thread(workflow.hypothesis.run, cleaned_df)
        hypotheses = hypothesis_result["hypotheses"]
        stats_summary = HypothesisBotAgent._build_stats_summary(cleaned_df)
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
            workflow.viz.run, cleaned_df, consensus, hypotheses=hypotheses
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
    # The full cleaned dataset is deliberately not returned: nothing in the
    # UI reads it, and on a large file it dominates the response body.
    import json as _json

    preview = {
        "columns": cleaned_df.columns.tolist(),
        "rows": _json.loads(cleaned_df.head(20).to_json(orient="records", date_format="iso")),
    }
    cleaner_response = {"report": cleaner_result["report"]}
    if sampling:
        cleaner_response["sampling"] = sampling

    return sanitize_json(
        {
            "cleaner": cleaner_response,
            "hypothesis": hypothesis_result,
            "debate": debate_result,
            "viz": viz_result,
            "narrative": summary_result.get("narrative", ""),
            "suggested_questions": summary_result.get("suggested_questions", []),
            "preview": preview,
            "sampling": sampling,
        }
    )


@router.post("/nlq")
async def natural_language_query(request: NLQRequest):
    """Natural language query with LLM-powered code generation."""
    sid = request.session_id
    path = resolve_dataset_path(request.dataset_id)

    try:
        # --- Phase 1: Data Janitor ---
        # Cleaning is deterministic, so a follow-up question reuses the
        # previous result instead of re-reading and re-cleaning the file.
        push_event(sid, agent_id="janitor", status="running")
        t0 = time.monotonic()

        def _clean():
            frame, notice = sample_for_analysis(read_frame(path))
            result = DataJanitorAgent(name="nlq_cleaner").run(frame)
            result["sampling"] = notice
            return result

        cleaned, from_cache = await asyncio.to_thread(get_cleaned, request.dataset_id, path, _clean)
        df = cleaned.df
        report = cleaned.report
        sampling = cleaned.sampling
        janitor_summary = (
            f"Removed {report.get('duplicates_removed', 0)} duplicates, "
            f"imputed {report.get('total_missing', 0)} missing values."
            + (" (cached)" if from_cache else "")
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
            "sampling": sampling,
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
    """Fetch data from BigQuery.

    Experimental: `google-cloud-bigquery` is an optional dependency and is
    not installed in the published images, so this returns 501 until an
    operator installs it. There is no UI for it yet either.
    """
    from app.utils.bigquery_utils import BigQueryUnavailableError, run_bigquery_query

    try:
        df = run_bigquery_query(request.credentials_json, request.query)
        path = os.path.join(DATASET_DIR, f"bq_{os.urandom(8).hex()}.csv")
        df.to_csv(path, index=False)
        dataset_id = _datasets.register(path, name="BigQuery result", source="bigquery")
        return {
            "dataset_id": dataset_id,
            "columns": df.columns.tolist(),
            "row_count": len(df),
        }
    except BigQueryUnavailableError as e:
        # Optional dependency absent — not a server fault, and not something
        # the caller can fix by changing the request.
        raise HTTPException(status_code=501, detail=str(e)) from e
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


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str):
    """Whether a dataset is still usable, and what it looks like.

    The UI calls this when reopening a saved workspace so it can say the
    data is gone up front, instead of restoring the charts and then failing
    on the user's next question.
    """
    try:
        path = _datasets.resolve_path(dataset_id)
    except DatasetMissingError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    record = _datasets.get(dataset_id)
    try:
        result = read_dataset(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return sanitize_json(
        {
            "dataset_id": dataset_id,
            "name": (record or {}).get("name", ""),
            "source": (record or {}).get("source", ""),
            **describe_dataset(result.df),
            "assumptions": result.assumptions,
        }
    )


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """Forget a dataset and remove its file."""
    if not _datasets.delete(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return {"status": "deleted"}


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
        path = os.path.join(DATASET_DIR, f"demo_{dataset_id}_{os.urandom(8).hex()}.csv")
        df.to_csv(path, index=False)
        # Recording the demo id lets the registry rebuild this file if it is
        # ever lost, so an old workspace reopens instead of dead-ending.
        registered_id = _datasets.register(path, name=metadata["name"], source=f"demo:{dataset_id}")

        return {
            "dataset_id": registered_id,
            "demo_id": metadata["dataset_id"],
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
