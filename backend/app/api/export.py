import csv
import io
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app.services.export_service import ExportService
from app.services.session_manager import get_session_manager

router = APIRouter(prefix="/export", tags=["export"])
export_service = ExportService()
_session_manager = get_session_manager()
logger = logging.getLogger(__name__)


def _parse_chart(plotly_json: str | None, title: str) -> dict | None:
    """Parse a stored Plotly figure JSON string into template-ready form."""
    if not plotly_json:
        return None
    try:
        fig = json.loads(plotly_json)
        return {
            "title": title,
            "data": fig.get("data", []),
            "layout": fig.get("layout", {}),
        }
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"Skipping unparseable chart in export: {e}")
        return None


def _build_session(session_id: str) -> dict:
    """Assemble a report payload from the real session history."""
    history = _session_manager.get(session_id)
    if not history:
        raise HTTPException(
            status_code=404,
            detail="No analysis found for this session (it may have expired).",
        )

    agents = []
    messages = []
    charts = []
    for entry in history:
        if entry.get("role") == "analysis":
            if entry.get("narrative"):
                messages.append({"role": "assistant", "content": entry["narrative"]})
            for h in entry.get("hypotheses", []) or []:
                if h is None:
                    continue
                text = h.get("hypothesis") if isinstance(h, dict) else str(h)
                if text:
                    agents.append({"emoji": "💡", "name": "Insight", "output": text})
            for c in entry.get("charts", []) or []:
                chart = _parse_chart(c.get("plotly_json"), c.get("title") or "Pipeline chart")
                if chart:
                    charts.append(chart)
        elif entry.get("question"):
            messages.append({"role": "user", "content": entry.get("question", "")})
            messages.append(
                {
                    "role": "assistant",
                    "content": entry.get("answer", ""),
                    "code": entry.get("code", ""),
                }
            )
            chart = _parse_chart(entry.get("plot_json"), entry.get("question", "Query chart"))
            if chart:
                charts.append(chart)

    return {
        "title": f"Analysis · {session_id}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agents": agents,
        "messages": messages,
        "charts": charts,
    }


@router.get("/{session_id}/html")
async def export_html(session_id: str):
    html = export_service.to_html(_build_session(session_id))
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f"attachment; filename=analysis-{session_id}.html"},
    )


@router.get("/{session_id}/markdown")
async def export_markdown(session_id: str):
    md = export_service.to_markdown(_build_session(session_id))
    return PlainTextResponse(
        content=md,
        headers={"Content-Disposition": f"attachment; filename=analysis-{session_id}.md"},
    )


@router.get("/{session_id}/csv")
async def export_qa_csv(session_id: str):
    """Export the session's question/answer/code history as CSV."""
    history = _session_manager.get(session_id)
    if not history:
        raise HTTPException(
            status_code=404,
            detail="No analysis found for this session (it may have expired).",
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["question", "answer", "code"])
    rows = 0
    for entry in history:
        if entry.get("question"):
            writer.writerow(
                [entry.get("question", ""), entry.get("answer", ""), entry.get("code", "")]
            )
            rows += 1
    if rows == 0:
        raise HTTPException(
            status_code=404, detail="No questions have been asked in this session yet."
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=qa-{session_id}.csv"},
    )
