from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from app.services.export_service import ExportService
from datetime import datetime

router = APIRouter(prefix="/export", tags=["export"])
export_service = ExportService()

# In a real database we'd fetch this from DB, but for this stateless architecture
# we generate a sample or take the payload in a different way.
# For demo purposes, we'll assume a dummy session generator or POST payload approach,
# or simply mock a generic return so the endpoints exist as requested.

def _get_mock_session(session_id: str):
    return {
        "title": f"Session Analysis: {session_id}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agents": [
            {"name": "Data Janitor", "emoji": "🧹", "output": "Cleaned 12 null rows..."},
            {"name": "Viz Whiz", "emoji": "📊", "output": "Generated sales trend chart..."}
        ],
        "messages": [
            {"role": "user", "content": "Show me sales by region"},
            {"role": "assistant", "content": "Here is the sales by region.", "code": "df.groupby('region')['sales'].sum()"}
        ],
        "charts": []
    }

@router.get("/{session_id}/html")
async def export_html(session_id: str):
    session = _get_mock_session(session_id)
    html = export_service.to_html(session)
    return HTMLResponse(content=html, headers={
        "Content-Disposition": f"attachment; filename=analysis-{session_id}.html"
    })

@router.get("/{session_id}/markdown")
async def export_markdown(session_id: str):
    session = _get_mock_session(session_id)
    md = export_service.to_markdown(session)
    return PlainTextResponse(content=md, headers={
        "Content-Disposition": f"attachment; filename=analysis-{session_id}.md"
    })

@router.get("/{session_id}/csv")
async def export_results_csv(session_id: str):
    """Export last query result as CSV. In stateless mode, mocks a response or relies on payload."""
    import pandas as pd
    import os
    
    # Generate mock CSV for export endpoint
    df = pd.DataFrame({"dummy": [1, 2, 3], "value": ["A", "B", "C"]})
    temp_path = f"/tmp/export_{session_id}.csv"
    df.to_csv(temp_path, index=False)
    
    return FileResponse(temp_path, filename=f"results-{session_id}.csv")
