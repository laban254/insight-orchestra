from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
import pandas as pd
from app.utils.file_utils import save_upload_file
from app.services.adk_agents import InsightOrchestraWorkflow
from app.services.nlq_agent import NaturalLanguageQueryAgent
from app.services.summarizer_agent import InsightSummarizerAgent
from app.services.explain_agent import ExplainabilityAgent
from app.services.report_agent import ReportGeneratorAgent
from app.services.llm_service import LLMService
from app.services.sandbox_executor import SandboxExecutor
import os

router = APIRouter()

# Session storage (in-memory for MVP, use Redis for production)
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
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
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
        context = _sessions.get(request.session_id, [])
    
    agent = NaturalLanguageQueryAgent()
    response = agent.run(df, request.question, context)
    
    # Store in session
    if request.session_id:
        if request.session_id not in _sessions:
            _sessions[request.session_id] = []
        _sessions[request.session_id].append({
            "question": request.question,
            "answer": response.answer,
            "code": response.code,
        })
        # Keep last 5 interactions
        _sessions[request.session_id] = _sessions[request.session_id][-5:]
    
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
    agent = InsightSummarizerAgent()
    return agent.run(workflow_results)


@router.post("/explain")
async def explain_plot(payload: dict):
    """Explain a visualization."""
    plot = payload.get("plot", {})
    agent = ExplainabilityAgent()
    return agent.run(plot)


@router.post("/report")
async def generate_report(payload: dict):
    """Generate HTML report."""
    workflow_results = payload.get("workflow_results", {})
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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session context."""
    return {"session_id": session_id, "history": _sessions.get(session_id, [])}


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear session context."""
    if session_id in _sessions:
        del _sessions[session_id]
    return {"status": "cleared"}


@router.get("/demo/load")
async def load_demo_data():
    """Load the built-in sales demo dataset."""
    from app.utils.demo_data import get_demo_dataset
    df = get_demo_dataset()
    temp_path = f"/tmp/demo_sales_{os.urandom(8).hex()}.csv"
    df.to_csv(temp_path, index=False)
    return {"file_path": temp_path, "columns": df.columns.tolist(), "row_count": len(df)}
