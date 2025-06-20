from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from pydantic import BaseModel
import pandas as pd
from app.utils.file_utils import save_upload_file
from app.services.adk_agents import InsightOrchestraWorkflow
from app.services.nlq_agent import NaturalLanguageQueryAgent
from app.services.summarizer_agent import InsightSummarizerAgent
from app.services.explain_agent import ExplainabilityAgent
from app.services.report_agent import ReportGeneratorAgent
import os

router = APIRouter()

@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    try:
        file_path = save_upload_file(file)
        return {"file_path": file_path}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="File upload failed.")

class ProcessRequest(BaseModel):
    file_path: str

@router.post("/process")
async def process_data(request: ProcessRequest):
    file_path = request.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to read CSV.")

    # Use ADK workflow
    workflow = InsightOrchestraWorkflow()
    results = workflow.run(df.to_dict(orient='records'))
    return results

@router.post("/nlq")
async def natural_language_query(payload: dict = Body(...)):
    file_path = payload["file_path"]
    question = payload["question"]
    df = pd.read_csv(file_path)
    agent = NaturalLanguageQueryAgent()
    return agent.run(df, question)

@router.post("/summarize")
async def summarize_insights(payload: dict = Body(...)):
    workflow_results = payload["workflow_results"]
    agent = InsightSummarizerAgent()
    return agent.run(workflow_results)

@router.post("/explain")
async def explain_plot(payload: dict = Body(...)):
    plot = payload["plot"]
    agent = ExplainabilityAgent()
    return agent.run(plot)

@router.post("/report")
async def generate_report(payload: dict = Body(...)):
    workflow_results = payload["workflow_results"]
    agent = ReportGeneratorAgent()
    return agent.run(workflow_results)