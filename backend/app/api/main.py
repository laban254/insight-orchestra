from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from app.services.adk_agents import InsightOrchestraWorkflow
from fastapi.staticfiles import StaticFiles
import pandas as pd
import uuid
import os

# --- New agent imports (to be implemented) ---
from app.services.nlq_agent import NaturalLanguageQueryAgent
from app.services.summarizer_agent import InsightSummarizerAgent
from app.services.explain_agent import ExplainabilityAgent
from app.services.report_agent import ReportGeneratorAgent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="/tmp"), name="static")

@app.post("/upload")
def upload(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    return {"file_path": file_path}

@app.post("/process")
def process(payload: dict):
    file_path = payload["file_path"]
    df = pd.read_csv(file_path)
    workflow = InsightOrchestraWorkflow()
    results = workflow.run(df.to_dict(orient="records"))
    # Return all agent results, including full chart_info for frontend
    return results

@app.post("/nlq")
def natural_language_query(payload: dict = Body(...)):
    """Answer a natural language question about the uploaded data."""
    file_path = payload["file_path"]
    question = payload["question"]
    df = pd.read_csv(file_path)
    agent = NaturalLanguageQueryAgent()
    return agent.run(df, question)

@app.post("/summarize")
def summarize_insights(payload: dict = Body(...)):
    """Summarize all insights from the workflow."""
    workflow_results = payload["workflow_results"]
    agent = InsightSummarizerAgent()
    return agent.run(workflow_results)

@app.post("/explain")
def explain_plot(payload: dict = Body(...)):
    """Explain a plot or hypothesis in plain language."""
    plot = payload["plot"]
    agent = ExplainabilityAgent()
    return agent.run(plot)

@app.post("/report")
def generate_report(payload: dict = Body(...)):
    """Generate a downloadable report from the workflow results."""
    workflow_results = payload["workflow_results"]
    agent = ReportGeneratorAgent()
    return agent.run(workflow_results)