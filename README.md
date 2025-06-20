# Insight Orchestra 2.0

**AI-powered, multi-agent data analysis for everyone.**

Insight Orchestra is an app that orchestrates multiple AI agents to analyze your data, generate insights, answer natural language questions, and produce beautiful reports—all.

---

## Features

- **Multi-Agent Orchestration:**
  - Data cleaning, hypothesis generation, debate, consensus, and more.
- **Natural Language Q&A:**
  - Ask questions about your data in plain English.
- **Automated Summarization:**
  - Get concise, business-friendly summaries of your data and findings.
- **Explainability:**
  - Plain-language explanations for charts and insights.
- **Smart Visualizations:**
  - Auto-generated charts with recommendations and next steps.
- **Report Generation:**
  - Download a full HTML report of your session.
- **Modern UI/UX:**
  - Sidebar navigation, hero section, progress bar, insight cards, copy-to-clipboard, and more.

---

## Quickstart

### 1. Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 2. Frontend (Streamlit)

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

- The frontend runs at `http://localhost:8501`
- The backend runs at `http://localhost:8000`

---

## Usage

You can analyze data from two sources:

### Option 1: Upload a CSV file
1. **Upload** your CSV file in the 'Upload & Status' section.
2. Click **Run Analysis** to let the agents work.

### Option 2: Connect to Google BigQuery
1. In the 'Upload & Status' section, select **Google BigQuery** as your data source.
2. Paste your Google service account credentials (JSON) and enter your SQL query.
3. Click **Fetch Data**. The app will securely connect, run your query, and load the results for analysis.

---

After loading your data (from CSV or BigQuery):

3. Explore the **Agent Feed** for data cleaning, hypotheses, and debate.
4. See **Summary & Q&A** for automated insights and ask questions in plain English.
5. Dive into **Visualizations** for auto-generated charts and explanations.
6. **Download** a full report of your session.

---

## Project Structure

```
backend/
  app/
    api/           # FastAPI endpoints
    services/      # Agent logic (NLQ, summarizer, explain, report)
    static/        # Static files (reports)
frontend/
  app.py           # Streamlit UI
```

---

## Usage Tips
- Use the sidebar for navigation and help.
- Try the natural language Q&A and chart explainability features.
- Download the report for a full session summary.

---

## License & Contact

MIT License. Made with ♥ by the Insight Orchestra team.

- [GitHub](https://github.com/laban254)
- Contact: labanrotich6544@gmail.com
