from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import pandas as pd
import asyncio
from sse_starlette.sse import EventSourceResponse
from app.utils.file_utils import save_upload_file
from app.services.adk_agents import InsightOrchestraWorkflow
from app.services.nlq_agent import NaturalLanguageQueryAgent
from app.services.summarizer_agent import InsightSummarizerAgent
from app.services.explain_agent import ExplainabilityAgent
from app.services.report_agent import ReportGeneratorAgent
from app.services.llm_service import LLMService
from app.services.sandbox_executor import SandboxExecutor
import os
import logging

logger = logging.getLogger(__name__)

# Demo mode flag - disable in production
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

router = APIRouter()

# Session manager (Redis-backed with in-memory fallback)
from app.services.session_manager import get_session_manager
_session_manager = get_session_manager()

# Legacy in-memory sessions (deprecated - use _session_manager)
_sessions = {}


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
    
    # Ensure the file is within allowed directories
    allowed_dirs = ['/tmp', 'uploads']
    real_path = os.path.realpath(file_path)
    if not any(real_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
        raise HTTPException(status_code=403, detail="Access denied: file outside allowed directories.")
    
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
async def process_data(request: ProcessRequest):
    """Run full Insight Orchestra workflow."""
    df = get_df(request.file_path)
    
    workflow = InsightOrchestraWorkflow()
    results = workflow.run(df.to_dict(orient='records'))
    return results


@router.post("/nlq")
async def natural_language_query(request: NLQRequest):
    """Natural language query with LLM-powered code generation."""
    df = get_df(request.file_path)
    
    # Get session context if provided
    context = None
    if request.session_id:
        context = _session_manager.get(request.session_id)
    
    agent = NaturalLanguageQueryAgent()
    response = agent.run(df, request.question, context)
    
    # Store in session
    if request.session_id:
        _session_manager.append(request.session_id, {
            "question": request.question,
            "answer": response.answer,
            "code": response.code,
        })
    
    return {
        "answer": response.answer,
        "code": response.code,
        "reasoning": response.reasoning,
        "plot_json": response.plot_json,
        "needs_clarification": response.needs_clarification,
        "clarification_question": response.clarification_question,
        "execution_success": response.execution_success,
        "error": response.error,
        "session_id": request.session_id,
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


@router.get("/demo/load")
async def load_demo_data():
    """Load the built-in sales demo dataset."""
    if not DEMO_MODE:
        raise HTTPException(
            status_code=404,
            detail="Demo endpoint disabled in production"
        )
    
    from app.utils.demo_data import get_demo_dataset
    df = get_demo_dataset()
    temp_path = f"/tmp/demo_sales_{os.urandom(8).hex()}.csv"
    df.to_csv(temp_path, index=False)
    return {"file_path": temp_path, "columns": df.columns.tolist(), "row_count": len(df)}


@router.get("/agents/stream/{session_id}")
async def stream_agent_logs(session_id: str):
    """Stream dummy agent progress logs for the UI."""
    async def log_generator():
        logs = [
            {"agent": "DataJanitorAgent", "message": "Cleaning dataset..."},
            {"agent": "HypothesisBotAgent", "message": "Generating hypotheses..."},
            {"agent": "DebateManagerAgent", "message": "Auditing hypotheses..."},
            {"agent": "VizWhizAgent", "message": "Generating visualizations..."},
            {"agent": "System", "message": "Workflow complete."}
        ]
        for log in logs:
            await asyncio.sleep(1.5)
            yield {"data": json.dumps(log)}

    import json
    return EventSourceResponse(log_generator())
