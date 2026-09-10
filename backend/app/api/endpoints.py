import asyncio
import json
import logging
import os
import time
from typing import Any, Literal

import pandas as pd
import requests
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent_progress import close_queue, get_queue, push_event, push_sentinel
from app.auth import require_role, require_user
from app.config import settings
from app.services.adk_agents import DataJanitorAgent, HypothesisBotAgent, InsightOrchestraWorkflow
from app.services.audit_log import get_audit_log_store
from app.services.dataset_cache import get_cleaned
from app.services.dataset_registry import (
    DATASET_DIR,
    DatasetMissingError,
    get_dataset_registry,
)
from app.services.llm_service import friendly_llm_error
from app.services.nlq_agent import NaturalLanguageQueryAgent, NLQResponse
from app.services.query_cache import get_query_cache
from app.services.session_manager import get_session_manager
from app.services.summarizer_agent import InsightSummarizerAgent
from app.services.user_store import Role, UserRecord
from app.utils.dataset_io import describe_dataset, read_dataset, sample_for_analysis
from app.utils.file_utils import discard_upload, save_upload_file
from app.utils.json_sanitize import sanitize_json

logger = logging.getLogger(__name__)

DEMO_MODE = settings.demo_mode

router = APIRouter()

# Session manager (Redis-backed with in-memory fallback)
_session_manager = get_session_manager()
_datasets = get_dataset_registry()
_audit = get_audit_log_store()


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
async def upload_csv(
    file: UploadFile = File(...), _user: UserRecord | None = Depends(require_role(Role.MEMBER))
):
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
async def process_data(
    request: ProcessRequest, _user: UserRecord | None = Depends(require_role(Role.MEMBER))
):
    """Run full Insight Orchestra workflow with real-time agent progress events."""
    path = resolve_dataset_path(request.dataset_id)
    workflow = InsightOrchestraWorkflow()
    sid = request.session_id

    async def _run_pipeline() -> dict:
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
        # Build the stats summary once and hand it to the hypothesis agent
        # (and, below, the debate agent) instead of recomputing describe()/
        # corr() at each stage.
        stats_summary = HypothesisBotAgent._build_stats_summary(cleaned_df)
        hypothesis_result = await asyncio.to_thread(
            workflow.hypothesis.run, cleaned_df, stats_summary
        )
        hypotheses = hypothesis_result["hypotheses"]
        push_event(
            sid,
            agent_id="hypothesis",
            status="done",
            output=(
                f"Found {len(hypotheses)} insights."
                if hypothesis_result.get("llm_used")
                else f"Surfaced {len(hypotheses)} descriptive pattern(s) — no LLM available."
            ),
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
        push_event(sid, agent_id="narrator", status="running")
        t0 = time.monotonic()
        summarizer = InsightSummarizerAgent(llm_service=workflow.llm)

        # Runs in a worker thread; push_event is safe to call from there
        # (see agent_progress.py) — each chunk updates the same "running"
        # event so the UI can show the narrative being written live instead
        # of only after the whole pipeline finishes.
        def _on_narrative_chunk(text: str) -> None:
            push_event(sid, agent_id="narrator", status="running", output=text)

        summary_result = await asyncio.to_thread(
            summarizer.run, workflow_results, _on_narrative_chunk
        )
        push_event(
            sid,
            agent_id="narrator",
            status="done",
            output=summary_result.get("narrative", ""),
            duration=int((time.monotonic() - t0) * 1000),
        )

        return {
            "cleaned_df": cleaned_df,
            "sampling": sampling,
            "cleaner_result": cleaner_result,
            "hypothesis_result": hypothesis_result,
            "hypotheses": hypotheses,
            "debate_result": debate_result,
            "consensus": consensus,
            "viz_result": viz_result,
            "summary_result": summary_result,
        }

    try:
        stages = await asyncio.wait_for(_run_pipeline(), timeout=settings.process_timeout_seconds)
    except HTTPException:
        # Deliberate error from deeper in the pipeline (e.g. a corrupt or
        # unreadable dataset) — already has the right status/message, so
        # don't let the generic handler below mask it behind a 502.
        push_sentinel(sid)
        raise
    except TimeoutError as e:
        # _run_pipeline() keeps executing in its background thread (Python
        # can't kill a thread), but the request itself fails fast with an
        # actionable message instead of hanging until the client gives up.
        push_event(sid, agent_id="pipeline", status="error", output="Analysis timed out.")
        push_sentinel(sid)
        raise HTTPException(
            status_code=504,
            detail=(
                "Analysis took too long and was stopped. Try a smaller dataset or a faster model."
            ),
        ) from e
    except Exception as e:
        logger.error(f"[session={sid}] /process failed: {e}")
        push_event(sid, agent_id="pipeline", status="error", output=str(e))
        push_sentinel(sid)
        # workflow.llm is None when no provider could be constructed at all
        # (e.g. no API key for any provider) — friendly_llm_error() needs a
        # real LLMService to name the provider, so fall back to a generic
        # message rather than passing None through.
        detail = (
            friendly_llm_error(e, workflow.llm)
            if workflow.llm is not None
            else "No LLM provider is configured. Set an API key in backend/.env and restart the backend."
        )
        raise HTTPException(status_code=502, detail=detail) from e
    else:
        push_sentinel(sid)

    cleaned_df = stages["cleaned_df"]
    sampling = stages["sampling"]
    cleaner_result = stages["cleaner_result"]
    hypothesis_result = stages["hypothesis_result"]
    hypotheses = stages["hypotheses"]
    debate_result = stages["debate_result"]
    consensus = stages["consensus"]
    viz_result = stages["viz_result"]
    summary_result = stages["summary_result"]

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
    # (Full pagination through the raw dataset is GET /datasets/{id}/rows.)
    preview = {
        "columns": cleaned_df.columns.tolist(),
        "rows": json.loads(cleaned_df.head(20).to_json(orient="records", date_format="iso")),
    }
    cleaner_response = {"report": cleaner_result["report"]}
    if sampling:
        cleaner_response["sampling"] = sampling

    from app import runtime_config

    # Each LLM-backed stage reports whether it actually reached the model. Surface that at the
    # top level: previously an LLM outage produced a normal 200 with heuristic output and no
    # way for any caller to tell the difference.
    stage_llm_used = {
        "hypothesis": hypothesis_result.get("llm_used", False),
        "debate": debate_result.get("llm_used", False),
        "narrative": summary_result.get("llm_used", False),
    }
    degraded_stages = sorted(name for name, used in stage_llm_used.items() if not used)

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
            "degraded": bool(degraded_stages),
            "degraded_stages": degraded_stages,
            "degraded_reason": (
                f"The {runtime_config.get_provider()} provider was unreachable or rejected the "
                f"request, so these stages fell back to statistics only: "
                f"{', '.join(degraded_stages)}. Results are descriptive, not interpreted."
                if degraded_stages
                else None
            ),
        }
    )


@router.post("/nlq")
async def natural_language_query(
    request: NLQRequest, _user: UserRecord | None = Depends(require_role(Role.MEMBER))
):
    """Natural language query with LLM-powered code generation."""
    sid = request.session_id
    path = resolve_dataset_path(request.dataset_id)
    sampling: dict[str, Any] | None = None

    async def _run() -> NLQResponse:
        nonlocal sampling
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

        from app import runtime_config

        cache = get_query_cache()
        provider = runtime_config.get_provider()
        model = runtime_config.current()["model"]
        cached = cache.get(request.dataset_id, request.question, provider, model, context)

        if cached is not None:
            response = NLQResponse(**cached)
            push_event(
                sid,
                agent_id="nlq",
                status="done",
                output="Generated and executed query successfully. (cached)",
                duration=int((time.monotonic() - t0) * 1000),
            )
        else:
            agent = NaturalLanguageQueryAgent()
            response = await asyncio.to_thread(agent.run, df, request.question, context, sid)
            if response.execution_success:
                cache.set(
                    request.dataset_id,
                    request.question,
                    provider,
                    model,
                    {
                        "answer": response.answer,
                        "code": response.code,
                        "reasoning": response.reasoning,
                        "plot_json": response.plot_json,
                        "needs_clarification": response.needs_clarification,
                        "clarification_question": response.clarification_question,
                        "execution_success": response.execution_success,
                        "error": response.error,
                    },
                    context,
                )
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
        return response

    try:
        response = await asyncio.wait_for(_run(), timeout=settings.nlq_timeout_seconds)
    except TimeoutError:
        # _run() keeps executing in its background thread (Python can't kill
        # a thread), but the request itself fails fast with an actionable
        # message instead of hanging until the client gives up on its own.
        push_event(sid, agent_id="nlq", status="error", output="Query timed out.")
        response = NLQResponse(
            answer=(
                "This query took too long and was stopped. Try a simpler question, a "
                "smaller dataset, or a faster model."
            ),
            code="",
            reasoning="",
            error="timeout",
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


@router.post("/bigquery")
async def bigquery_fetch(
    request: BigQueryRequest, _user: UserRecord | None = Depends(require_role(Role.MEMBER))
):
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


# POST /config switches the live provider/model for everyone, so it (and GET,
# which reveals which providers have keys configured) is admin-only once
# AUTH_ENABLED=True. With auth off — the default, single-tenant/localhost
# case — require_role() is a no-op and this stays open, as before.
class ConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None


# Values shipped in .env.example that mean "unset". Kept in one place so the readiness
# report and the switch guard cannot drift apart — they previously used different checks,
# so GET /config advertised openai as ready while POST /config rejected it with a 400.
_PLACEHOLDER_KEYS = frozenset(
    {"sk-...", "sk-ant-...", "your-openai-api-key-here", "your-api-key-here"}
)


def _api_key_configured(key: str | None) -> bool:
    """True if `key` is a real credential rather than blank or a template placeholder."""
    if not key:
        return False
    k = key.strip()
    return bool(k) and k not in _PLACEHOLDER_KEYS and "your-" not in k.lower()


def _ollama_reachable(timeout: float = 1.0) -> bool:
    """Probe the Ollama daemon. Reported readiness used to be hardcoded True, so the UI
    offered Ollama even with no daemon running and the pipeline silently degraded."""
    try:
        resp = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=timeout)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _provider_readiness() -> dict[str, bool]:
    """Single source of truth for which providers can actually serve a request."""
    return {
        "openai": _api_key_configured(settings.openai_api_key),
        "anthropic": _api_key_configured(settings.anthropic_api_key),
        "deepseek": _api_key_configured(settings.deepseek_api_key),
        "ollama": _ollama_reachable(),
    }


@router.get("/config")
async def get_config(_user: UserRecord | None = Depends(require_role(Role.ADMIN))):
    """Current LLM provider/model and what's switchable."""
    from app import runtime_config

    ready = await asyncio.to_thread(_provider_readiness)
    return {
        **runtime_config.current(),
        "available": runtime_config.PROVIDERS,
        "ready": ready,
    }


@router.post("/config")
async def update_config(
    update: ConfigUpdate,
    user: UserRecord | None = Depends(require_role(Role.ADMIN)),
):
    """Switch provider/model at runtime (no restart needed)."""
    from app import runtime_config

    if update.provider and update.provider not in runtime_config.PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{update.provider}'.")
    prov = update.provider or runtime_config.get_provider()
    ready = await asyncio.to_thread(_provider_readiness)
    if not ready.get(prov, False):
        detail = (
            f"Ollama is not reachable at {settings.ollama_base_url}."
            if prov == "ollama"
            else f"No API key configured for '{prov}' on the server."
        )
        raise HTTPException(status_code=400, detail=detail)
    runtime_config.set_override(update.provider, update.model)
    if user is not None:
        _audit.record(
            "config_change",
            actor_user_id=user["id"],
            actor_email=user["email"],
            detail={"provider": update.provider, "model": update.model},
        )
    return runtime_config.current()


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str, _user: UserRecord | None = Depends(require_user)):
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
            "name": record["name"] if record else "",
            "source": record["source"] if record else "",
            **describe_dataset(result.df),
            "assumptions": result.assumptions,
        }
    )


# Every other preview in the API (`/upload`, `GET /datasets/{id}`) is a fixed
# `head(20)` — fine for "does this look right after ingest" but no way to
# see the rest of a large file. This is the one place that can page through
# the whole thing.
MAX_PAGE_SIZE = 500


@router.get("/datasets/{dataset_id}/rows")
async def get_dataset_rows(
    dataset_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    _user: UserRecord | None = Depends(require_user),
):
    """A page of rows from the dataset, for browsing past the fixed preview."""
    df = get_df(dataset_id)
    total_rows = len(df)
    page = df.iloc[offset : offset + limit]

    return sanitize_json(
        {
            "columns": df.columns.tolist(),
            "rows": json.loads(page.to_json(orient="records", date_format="iso")),
            "total_rows": total_rows,
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total_rows,
        }
    )


class TransformRequest(BaseModel):
    column: str
    operation: Literal["normalize", "scale", "encode"]
    # Defaults to "{column}_{operation}" if not given.
    new_column: str | None = None


@router.post("/datasets/{dataset_id}/transform")
async def transform_dataset(
    dataset_id: str,
    request: TransformRequest,
    _user: UserRecord | None = Depends(require_role(Role.MEMBER)),
):
    """Apply a deterministic column transform, without needing the LLM to
    write and run pandas code for what's really a fixed, well-known
    operation. Non-destructive: writes the result as a new derived dataset
    rather than mutating the original, consistent with every other
    ingestion path (upload/demo/DB table) always minting a fresh id.
    """
    df = get_df(dataset_id)
    if request.column not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{request.column}' not found.")

    new_column = request.new_column or f"{request.column}_{request.operation}"
    series = df[request.column]
    result_df = df.copy()

    if request.operation in ("normalize", "scale"):
        if not pd.api.types.is_numeric_dtype(series):
            raise HTTPException(
                status_code=400,
                detail=f"'{request.operation}' needs a numeric column; "
                f"'{request.column}' is {series.dtype}.",
            )
        if request.operation == "normalize":
            lo, hi = series.min(), series.max()
            # A constant column has no range to normalize against — every
            # value is equally "the middle" rather than a divide-by-zero.
            result_df[new_column] = 0.5 if hi == lo else (series - lo) / (hi - lo)
        else:  # scale (z-score / standardize)
            mean, std = series.mean(), series.std()
            result_df[new_column] = 0.0 if not std else (series - mean) / std
    else:  # encode — integer-code each distinct value, in first-seen order
        codes, _ = pd.factorize(series.astype(str))
        result_df[new_column] = codes

    path = os.path.join(DATASET_DIR, f"transform_{os.urandom(8).hex()}.csv")
    result_df.to_csv(path, index=False)
    record = _datasets.get(dataset_id)
    base_name = record["name"] if record else dataset_id
    new_dataset_id = _datasets.register(
        path, name=f"{base_name} ({request.operation}: {request.column})", source="transform"
    )

    return sanitize_json(
        {
            "dataset_id": new_dataset_id,
            "new_column": new_column,
            "operation": request.operation,
            **describe_dataset(result_df),
        }
    )


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    user: UserRecord | None = Depends(require_role(Role.MEMBER)),
):
    """Forget a dataset and remove its file."""
    if not _datasets.delete(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if user is not None:
        _audit.record(
            "dataset_delete",
            actor_user_id=user["id"],
            actor_email=user["email"],
            resource=dataset_id,
        )
    return {"status": "deleted"}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, _user: UserRecord | None = Depends(require_user)):
    """Get session context."""
    return {"session_id": session_id, "history": _session_manager.get(session_id)}


@router.delete("/sessions/{session_id}")
async def clear_session(
    session_id: str, _user: UserRecord | None = Depends(require_role(Role.MEMBER))
):
    """Clear session context."""
    _session_manager.delete(session_id)
    return {"status": "cleared"}


@router.get("/demo/list")
async def list_demo_datasets(_user: UserRecord | None = Depends(require_user)):
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
async def load_demo_data(
    dataset_id: str = "sales", _user: UserRecord | None = Depends(require_role(Role.MEMBER))
):
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
async def stream_agent_logs(session_id: str, _user: UserRecord | None = Depends(require_user)):
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
